"""Instrumented, fault-tolerant Celery task publishing.

Centralises every "send a task to the broker" call so that:
  * publish latency, enqueue counts and failure counts are recorded once,
  * RabbitMQ connectivity failures are turned into a single, well-typed
    ``BrokerPublishError`` (instead of leaking kombu/socket internals), and
  * publishing fails *fast* rather than hanging when the broker is down.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from amqp.exceptions import AMQPError
from kombu.exceptions import KombuError
from kombu.exceptions import OperationalError as KombuOperationalError

from app.core import metrics
from app.core.config import settings

logger = logging.getLogger("app.task_publisher")

# Every error class that means "the broker could not accept this task".
BROKER_ERRORS: tuple[type[BaseException], ...] = (
    KombuOperationalError,
    KombuError,
    AMQPError,
    ConnectionError,
    ConnectionRefusedError,
    TimeoutError,
    OSError,
)


class BrokerPublishError(RuntimeError):
    """Raised when a task could not be published to the broker."""

    def __init__(self, message: str, original: Optional[BaseException] = None):
        super().__init__(message)
        self.original = original


def _retry_policy() -> dict:
    """Bounded exponential-ish policy for transient broker publish failures."""
    return {
        "max_retries": settings.publish_max_retries,
        "interval_start": 0.2,
        "interval_step": 0.4,
        "interval_max": 2.0,
    }


def enqueue(
    task,
    *,
    queue: str,
    kwargs: Optional[dict] = None,
    task_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
):
    """Publish ``task`` to ``queue`` durably, with metrics + graceful handling.

    Reliability guarantees:
      * **durable**: published as a persistent message onto a durable queue,
      * **confirmed**: broker publisher-confirms are enabled globally
        (``broker_transport_options={"confirm_publish": True}``),
      * **retried**: transient broker failures are retried per ``_retry_policy``
        before giving up.

    Returns the Celery ``AsyncResult`` on success.
    Raises ``BrokerPublishError`` if the broker stays unreachable.
    """
    task_name = getattr(task, "name", str(task))
    labels = {"task": task_name, "queue": queue}
    correlation_id = correlation_id or task_id

    metrics.task_publish_inflight.labels(**labels).inc()
    start = time.perf_counter()
    try:
        async_result = task.apply_async(
            kwargs=kwargs or {},
            task_id=task_id,
            queue=queue,
            # Persistent message on a durable queue => survives broker restart.
            delivery_mode=2,
            # Retry the publish on transient broker connectivity failures.
            retry=True,
            retry_policy=_retry_policy(),
        )
    except BROKER_ERRORS as exc:
        metrics.task_publish_failures_total.labels(
            **labels, error_type=type(exc).__name__
        ).inc()
        logger.error(
            "broker connection failure while publishing task=%s queue=%s "
            "correlation_id=%s: %s",
            task_name,
            queue,
            correlation_id,
            exc,
        )
        raise BrokerPublishError(
            f"Broker unavailable while publishing {task_name}: {exc}", original=exc
        ) from exc
    else:
        elapsed = time.perf_counter() - start
        metrics.task_publish_latency_seconds.labels(**labels).observe(elapsed)
        metrics.task_enqueued_total.labels(**labels).inc()
        logger.info(
            "queue publish success task=%s queue=%s task_id=%s correlation_id=%s "
            "latency_ms=%.1f",
            task_name,
            queue,
            async_result.id,
            correlation_id,
            elapsed * 1000,
        )
        return async_result
    finally:
        metrics.task_publish_inflight.labels(**labels).dec()
