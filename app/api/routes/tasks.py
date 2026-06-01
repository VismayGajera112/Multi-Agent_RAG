"""Task status endpoint.

Lightweight lookup of a Celery task's state by ``task_id`` (complements the
document-centric ``GET /ingest/{document_id}``). Useful for the frontend's
processing tracker.
"""

import logging

from fastapi import APIRouter

from app.core.celery_app import celery_app

logger = logging.getLogger("app.tasks_api")
router = APIRouter()

# Map Celery's internal states to a small, frontend-friendly vocabulary.
_FRIENDLY = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "processing",
    "RETRY": "processing",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """Return the status of a Celery task.

    {
      "task_id": "...",
      "status": "processing",
      "celery_state": "STARTED",
      "ready": false,
      "successful": null
    }
    """
    result = celery_app.AsyncResult(task_id)
    state = result.state
    ready = result.ready()
    payload = {
        "task_id": task_id,
        "status": _FRIENDLY.get(state, state.lower()),
        "celery_state": state,
        "ready": ready,
        "successful": result.successful() if ready else None,
    }
    if ready and result.successful():
        try:
            payload["result"] = result.result
        except Exception:  # noqa: BLE001 - result may not be serialisable
            payload["result"] = None
    return payload
