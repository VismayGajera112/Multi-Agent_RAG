"""Async chat-analytics consumer.

The chat API publishes one analytics event per request (query, latency, token
usage, retrieval hit count) to ``chat_analytics_queue``. This task consumes
them off the worker, persists a capped history in Redis, and exposes a consumed
counter — demonstrating an event-driven analytics pipeline fully decoupled from
the request path.
"""

from __future__ import annotations

import logging

from celery.exceptions import Reject

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import push_chat_analytics

logger = logging.getLogger("app.tasks.analytics")

TASK_NAME = "app.tasks.analytics_tasks.record_chat_analytics"


@celery_app.task(
    name=TASK_NAME,
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
)
def record_chat_analytics(self, event: dict) -> dict:
    """Persist a single chat analytics event."""
    from app.core import worker_metrics as wm

    if not isinstance(event, dict) or "query" not in event:
        # Malformed analytics payload — poison message, send to DLQ.
        logger.error("malformed chat analytics event task_id=%s", self.request.id)
        raise Reject(requeue=False)

    try:
        push_chat_analytics(event, max_len=settings.chat_analytics_history_max)
    except Exception as exc:  # noqa: BLE001 - transient redis blip => retry
        logger.warning("failed to persist chat analytics, retrying: %s", exc)
        raise self.retry(exc=exc, countdown=2)

    wm.chat_analytics_consumed_total.inc()
    logger.info(
        "chat analytics recorded session_id=%s latency_ms=%s tokens=%s hits=%s",
        event.get("session_id"),
        event.get("latency_ms"),
        event.get("total_tokens"),
        event.get("retrieval_hits"),
    )
    return {"recorded": True, "session_id": event.get("session_id")}
