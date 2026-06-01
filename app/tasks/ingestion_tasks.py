"""PDF ingestion + Gemini embedding pipeline (Celery consumer).

Message payload (published by the upload API):

    {
        "task_id":     "...",   # Celery task id (correlation)
        "document_id": "...",   # logical document id
        "file_path":   "...",   # path on the shared upload volume
        "uploaded_at": "..."    # ISO-8601 timestamp
    }

Pipeline:  parse PDF -> chunk -> embed (Gemini) -> upsert vectors into Qdrant.

Reliability:
  * acks_late + reject_on_worker_lost  -> survives worker crashes
  * transient failures (Gemini rate limits, Qdrant write errors, network)
    are retried with exponential back-off + jitter, up to max_retries=5
  * poison messages (malformed/missing PDF) and retry-exhausted tasks are
    routed to the DLQ via ``Reject(requeue=False)`` + the queue's DLX.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone

from celery.exceptions import Reject, SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.embeddings import embed_texts
from app.core.ingestion_errors import (
    EmbeddingRateLimitError,
    PermanentIngestionError,
    QdrantWriteError,
    TransientIngestionError,
)
from app.core.pdf_parser import chunk_text, extract_text
from app.core.qdrant_client import upsert_chunks
from app.core.redis_client import set_ingestion_state

logger = logging.getLogger("app.tasks.ingestion")

TASK_NAME = "app.tasks.ingestion_tasks.ingest_pdf"


def _backoff_countdown(retries: int) -> int:
    """Exponential back-off with jitter (seconds)."""
    base = settings.celery_retry_backoff_base
    ceiling = min(base ** (retries + 1), settings.celery_retry_backoff_max)
    # Full jitter: random point in (ceiling/2, ceiling] to avoid thundering herds.
    return max(1, int(random.uniform(ceiling / 2, ceiling)))


def _to_dlq(task, document_id: str, reason: str, exc: Exception):
    """Record DLQ routing + reject the message so RabbitMQ dead-letters it."""
    from app.core import worker_metrics as wm

    short_reason = reason.split(":", 1)[0]
    wm.dead_letter_total.labels(task=TASK_NAME, reason=short_reason).inc()
    wm.tasks_processed_total.labels(task=TASK_NAME, status="dead_letter").inc()
    set_ingestion_state(
        document_id,
        {
            "status": "DEAD_LETTER",
            "task_id": task.request.id,
            "reason": reason,
            "error": str(exc),
        },
    )
    logger.error(
        "task moved to DLQ document_id=%s task_id=%s reason=%s error=%s",
        document_id,
        task.request.id,
        reason,
        exc,
    )
    # acks_late + queue x-dead-letter-exchange => message lands in dead_letter_queue.
    raise Reject(requeue=False)


def _retry_or_dlq(task, document_id: str, exc: Exception, reason: str):
    """Retry transient failures with back-off; dead-letter once exhausted."""
    from app.core import worker_metrics as wm

    retries = task.request.retries
    if retries >= task.max_retries:
        return _to_dlq(task, document_id, f"retries_exhausted:{reason}", exc)

    countdown = _backoff_countdown(retries)
    wm.task_retries_total.labels(task=TASK_NAME, reason=reason).inc()
    set_ingestion_state(
        document_id,
        {
            "status": "RETRY",
            "task_id": task.request.id,
            "reason": reason,
            "attempt": retries + 1,
            "next_retry_in_s": countdown,
            "error": str(exc),
        },
    )
    logger.warning(
        "retry scheduled document_id=%s task_id=%s reason=%s attempt=%d/%d "
        "countdown=%ds error=%s",
        document_id,
        task.request.id,
        reason,
        retries + 1,
        task.max_retries,
        countdown,
        exc,
    )
    raise task.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name=TASK_NAME,
    bind=True,
    acks_late=True,
    max_retries=settings.celery_max_retries,  # 5
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max,
    retry_jitter=True,
)
def ingest_pdf(
    self,
    document_id: str,
    file_path: str,
    uploaded_at: str | None = None,
    collection: str | None = None,
) -> dict:
    """Consume one ingestion job: parse -> embed -> upsert into Qdrant."""
    from app.core import worker_metrics as wm

    wm.tasks_received_total.labels(task=TASK_NAME).inc()
    logger.info(
        "task received document_id=%s task_id=%s file_path=%s attempt=%d",
        document_id,
        self.request.id,
        file_path,
        self.request.retries,
    )

    started_at = datetime.now(timezone.utc).isoformat()
    set_ingestion_state(
        document_id,
        {
            "status": "STARTED",
            "task_id": self.request.id,
            "file_path": file_path,
            "uploaded_at": uploaded_at,
            "started_at": started_at,
        },
    )

    t0 = time.monotonic()
    try:
        text = extract_text(file_path)
        chunks = chunk_text(text)

        wm.embedding_requests_total.inc()
        vectors = embed_texts(chunks)
        wm.chunks_embedded_total.inc(len(chunks))

        written = upsert_chunks(
            document_id,
            chunks,
            vectors,
            collection=collection,
            extra_payload={"uploaded_at": uploaded_at},
        )
    except PermanentIngestionError as exc:
        # Poison message — never retry.
        return _to_dlq(self, document_id, f"permanent:{type(exc).__name__}", exc)
    except EmbeddingRateLimitError as exc:
        wm.embedding_rate_limited_total.inc()
        return _retry_or_dlq(self, document_id, exc, reason="rate_limit")
    except QdrantWriteError as exc:
        wm.qdrant_write_failures_total.inc()
        return _retry_or_dlq(self, document_id, exc, reason="qdrant_write")
    except TransientIngestionError as exc:
        return _retry_or_dlq(self, document_id, exc, reason="transient")
    except SoftTimeLimitExceeded as exc:
        return _retry_or_dlq(self, document_id, exc, reason="soft_time_limit")
    except Reject:
        raise  # already handled by _to_dlq
    except Exception as exc:  # noqa: BLE001 - unexpected => retry, then DLQ
        return _retry_or_dlq(self, document_id, exc, reason="unexpected")

    duration = time.monotonic() - t0
    wm.task_processing_seconds.labels(task=TASK_NAME).observe(duration)
    wm.tasks_processed_total.labels(task=TASK_NAME, status="success").inc()

    result = {
        "document_id": document_id,
        "file_path": file_path,
        "uploaded_at": uploaded_at,
        "collection": collection or settings.qdrant_collection,
        "chunks_indexed": written,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int(duration * 1000),
    }
    set_ingestion_state(
        document_id, {"status": "SUCCESS", "task_id": self.request.id, "result": result}
    )
    logger.info(
        "task completion document_id=%s task_id=%s chunks=%d duration_ms=%d",
        document_id,
        self.request.id,
        written,
        result["duration_ms"],
    )
    return result
