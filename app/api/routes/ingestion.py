import logging
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core import metrics
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import get_ingestion_state, set_ingestion_state
from app.core.task_publisher import BrokerPublishError, enqueue
from app.schemas.ingestion import (
    IngestionAcceptedResponse,
    IngestionRequest,
    IngestionStatusResponse,
    UploadAcceptedResponse,
)
from app.tasks.ingestion_tasks import ingest_pdf

logger = logging.getLogger("app.ingestion")
router = APIRouter()

PDF_INGESTION_QUEUE = "pdf_ingestion_queue"
PDF_MAGIC = b"%PDF"


def _reject(reason: str, status_code: int, detail: str) -> HTTPException:
    metrics.uploads_rejected_total.labels(reason=reason).inc()
    return HTTPException(status_code=status_code, detail=detail)


@router.post("/upload", status_code=202, response_model=UploadAcceptedResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Asynchronous PDF upload (write path).

    Validates the upload, persists it to the shared upload volume, generates
    document/task IDs, publishes a durable Celery task to RabbitMQ, and returns
    immediately — the endpoint never waits for ingestion to run.
    """
    received_at = time.perf_counter()

    # ---- 1. validate upload ------------------------------------------------
    filename = file.filename or "upload.pdf"
    is_pdf_name = filename.lower().endswith(".pdf")
    is_pdf_type = (file.content_type or "").lower() in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    )
    if not (is_pdf_name or is_pdf_type):
        raise _reject("bad_content_type", 415, "Only PDF uploads are accepted.")

    # Read with a hard size cap (read one extra byte to detect overflow).
    contents = await file.read(settings.max_upload_bytes + 1)
    if len(contents) == 0:
        raise _reject("empty_file", 400, "Uploaded file is empty.")
    if len(contents) > settings.max_upload_bytes:
        raise _reject(
            "too_large",
            413,
            f"File exceeds max size of {settings.max_upload_bytes} bytes.",
        )
    if not contents.startswith(PDF_MAGIC):
        raise _reject("not_a_pdf", 415, "File content is not a valid PDF.")

    # ---- 2. generate IDs + persist temporary file --------------------------
    document_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()
    file_path = os.path.join(settings.upload_dir, f"{document_id}.pdf")

    def _persist() -> None:
        os.makedirs(settings.upload_dir, exist_ok=True)
        with open(file_path, "wb") as fh:
            fh.write(contents)

    try:
        await run_in_threadpool(_persist)
    except OSError as exc:
        raise _reject("persist_failed", 500, f"Could not persist upload: {exc}")

    # ---- 3. publish Celery task (durable + confirmed + retried) ------------
    payload = {
        "task_id": task_id,
        "document_id": document_id,
        "file_path": file_path,
        "uploaded_at": uploaded_at,
    }
    try:
        # Offload the (blocking, possibly retrying) publish so the event loop
        # stays free — the endpoint remains non-blocking.
        await run_in_threadpool(
            lambda: enqueue(
                ingest_pdf,
                queue=PDF_INGESTION_QUEUE,
                kwargs={
                    "document_id": document_id,
                    "file_path": file_path,
                    "uploaded_at": uploaded_at,
                    "collection": None,
                },
                task_id=task_id,
                correlation_id=document_id,
            )
        )
    except BrokerPublishError as exc:
        # Clean up the orphaned file; surface a retryable 503 (never a 500).
        try:
            os.remove(file_path)
        except OSError:
            pass
        logger.error(
            "upload publish failed document_id=%s task_id=%s: %s",
            document_id,
            task_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Task broker is unavailable, please retry shortly.",
        ) from exc

    # ---- 4. record state + observability, return async response ------------
    set_ingestion_state(
        document_id,
        {
            "status": "PENDING",
            "task_id": task_id,
            "file_path": file_path,
            "uploaded_at": uploaded_at,
            "filename": filename,
            "size_bytes": len(contents),
        },
    )
    elapsed = time.perf_counter() - received_at
    metrics.upload_to_queue_duration_seconds.labels(queue=PDF_INGESTION_QUEUE).observe(
        elapsed
    )
    metrics.uploads_accepted_total.labels(queue=PDF_INGESTION_QUEUE).inc()
    logger.info(
        "upload accepted document_id=%s task_id=%s filename=%s size=%d "
        "upload_to_queue_ms=%.1f",
        document_id,
        task_id,
        filename,
        len(contents),
        elapsed * 1000,
    )

    return UploadAcceptedResponse(
        document_id=document_id,
        task_id=task_id,
        filename=filename,
        size_bytes=len(contents),
        uploaded_at=uploaded_at,
        upload_to_queue_ms=round(elapsed * 1000, 2),
    )


@router.post("", status_code=202, response_model=IngestionAcceptedResponse)
async def submit_ingestion(payload: IngestionRequest):
    """JSON enqueue path for an already-available file/URI (non-upload)."""
    document_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()

    try:
        await run_in_threadpool(
            lambda: enqueue(
                ingest_pdf,
                queue=PDF_INGESTION_QUEUE,
                kwargs={
                    "document_id": document_id,
                    "file_path": payload.document_uri,
                    "uploaded_at": uploaded_at,
                    "collection": payload.collection,
                },
                task_id=task_id,
                correlation_id=document_id,
            )
        )
    except BrokerPublishError as exc:
        raise HTTPException(
            status_code=503,
            detail="Task broker is unavailable, please retry shortly.",
        ) from exc

    set_ingestion_state(
        document_id,
        {"status": "PENDING", "task_id": task_id, "file_path": payload.document_uri},
    )
    return IngestionAcceptedResponse(document_id=document_id, task_id=task_id)


@router.get("/{document_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(document_id: str):
    """Return ingestion status from Redis state + Celery result backend."""
    try:
        uuid.UUID(document_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid document_id") from exc

    state = get_ingestion_state(document_id) or {}
    task_id = state.get("task_id")

    # DEAD_LETTER is an app-owned terminal state: a Reject(requeue=False) does
    # not produce a terminal Celery result, so trust the Redis state here.
    if state.get("status") == "DEAD_LETTER":
        return IngestionStatusResponse(
            document_id=document_id,
            task_id=task_id,
            status="DEAD_LETTER",
            error=f"{state.get('reason')}: {state.get('error')}",
        )

    if task_id:
        async_result = celery_app.AsyncResult(task_id)
        celery_state = async_result.state
        if celery_state == "SUCCESS":
            return IngestionStatusResponse(
                document_id=document_id,
                task_id=task_id,
                status="SUCCESS",
                result=async_result.result,
            )
        if celery_state == "FAILURE":
            return IngestionStatusResponse(
                document_id=document_id,
                task_id=task_id,
                status="FAILURE",
                error=str(async_result.result),
            )
        return IngestionStatusResponse(
            document_id=document_id, task_id=task_id, status=celery_state
        )

    return IngestionStatusResponse(
        document_id=document_id,
        status=state.get("status", "PENDING"),
        result=state.get("result"),
        error=state.get("error"),
    )
