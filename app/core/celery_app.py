"""Shared Celery application.

Topology note
-------------
The durable queues (``pdf_ingestion_queue``, ``embedding_retry_queue``,
``dead_letter_queue``) and the dead-letter exchange are declared
*authoritatively* by RabbitMQ from ``rabbitmq/definitions.json`` at broker
boot. Celery is configured here **not** to redeclare those queues with
conflicting arguments — it only references them by name and binds its
routes to them. This avoids ``PRECONDITION_FAILED`` (inequivalent arg)
errors that occur when two parties declare the same queue differently.
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

celery_app = Celery("multi_agent_rag")

# ---------------------------------------------------------------------------
# Queue / exchange topology — must mirror rabbitmq/definitions.json.
# ``durable=True`` + ``no_declare=True`` => Celery uses the queues that
# RabbitMQ already created from definitions.json instead of declaring them.
# ---------------------------------------------------------------------------
pdf_ingestion_exchange = Exchange("pdf_ingestion_exchange", type="direct", durable=True)
chat_analytics_exchange = Exchange("chat_analytics_exchange", type="direct", durable=True)
dead_letter_exchange = Exchange("dead_letter_exchange", type="direct", durable=True)

task_queues = (
    # Default queue Celery uses for everything not explicitly routed.
    Queue("celery", Exchange("celery", type="direct", durable=True), routing_key="celery", durable=True),
    # Pre-provisioned ingestion queue (declared by RabbitMQ definitions.json).
    Queue(
        "pdf_ingestion_queue",
        pdf_ingestion_exchange,
        routing_key="pdf_ingestion",
        durable=True,
        no_declare=True,
    ),
    # Async chat-analytics events published by the (independent) chat API.
    Queue(
        "chat_analytics_queue",
        chat_analytics_exchange,
        routing_key="chat_analytics",
        durable=True,
        no_declare=True,
    ),
    # Dead-letter sink — surfaced in the RabbitMQ UI for inspection.
    Queue(
        "dead_letter_queue",
        dead_letter_exchange,
        routing_key="dead_letter",
        durable=True,
        no_declare=True,
    ),
)

celery_app.conf.update(
    # ------------------------------------------------------------------
    # Transport / backend
    # ------------------------------------------------------------------
    broker_url=settings.rabbitmq_url,
    result_backend=settings.redis_url,
    # Explicitly import task modules so they register in the worker process.
    imports=("app.tasks.ingestion_tasks", "app.tasks.analytics_tasks"),
    # Keep retrying the broker connection while RabbitMQ finishes booting —
    # essential under docker-compose service-ordering.
    broker_connection_retry_on_startup=True,
    # Publisher confirms: don't consider a task "sent" until the broker acks.
    broker_transport_options={"confirm_publish": True},
    result_expires=3600,

    # ------------------------------------------------------------------
    # Serialization — JSON only; never pickle.
    # ------------------------------------------------------------------
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_task_serializer,
    accept_content=[settings.celery_task_serializer],

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------
    task_queues=task_queues,
    task_default_queue="celery",
    task_default_exchange="celery",
    task_default_routing_key="celery",
    task_routes={
        "app.tasks.ingestion_tasks.ingest_pdf": {
            "queue": "pdf_ingestion_queue",
            "routing_key": "pdf_ingestion",
        },
        "app.tasks.analytics_tasks.record_chat_analytics": {
            "queue": "chat_analytics_queue",
            "routing_key": "chat_analytics",
        },
    },

    # ------------------------------------------------------------------
    # Reliability / acknowledgement semantics
    #   * acks_late: ack only after the task finishes (survives worker crash)
    #   * reject_on_worker_lost: requeue if the worker dies mid-task
    #   * acks_on_failure_or_timeout: a plain failure still acks; the task
    #     itself raises Reject(requeue=False) to dead-letter poison messages.
    # ------------------------------------------------------------------
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
    worker_prefetch_multiplier=1,

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,

    # ------------------------------------------------------------------
    # Retry policy + exponential back-off defaults (per-task overridable).
    # ------------------------------------------------------------------
    task_default_retry_delay=settings.celery_retry_backoff_base,
    task_annotations={
        "*": {
            "max_retries": settings.celery_max_retries,
            "retry_backoff": settings.celery_retry_backoff_base,
            "retry_backoff_max": settings.celery_retry_backoff_max,
            "retry_jitter": True,
        }
    },

    # ------------------------------------------------------------------
    # Observability — emit events so celery-exporter / Flower can track tasks.
    # ------------------------------------------------------------------
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,

    timezone="UTC",
    enable_utc=True,
)

# Also auto-discover any future `tasks.py` modules under the app package.
celery_app.autodiscover_tasks(["app"])


def queue_backlog(queue: str, timeout: float = 3.0) -> int | None:
    """Return the number of ready messages in ``queue`` (broker backlog).

    Uses a passive ``queue_declare`` so it never mutates topology. Returns
    ``None`` if the broker can't be reached.
    """
    try:
        conn = celery_app.connection(connect_timeout=timeout)
        try:
            conn.ensure_connection(max_retries=0, timeout=timeout)
            _, message_count, _ = conn.default_channel.queue_declare(
                queue=queue, passive=True
            )
            return int(message_count)
        finally:
            conn.release()
    except Exception:
        return None


def check_broker(timeout: float = 3.0) -> bool:
    """Best-effort RabbitMQ connectivity probe used by the readiness endpoint.

    Opens a short-lived broker connection and fails fast (no retry loop) so a
    dead broker turns into a quick "degraded" readiness response rather than a
    hanging request.
    """
    try:
        conn = celery_app.connection(connect_timeout=timeout)
        try:
            conn.ensure_connection(max_retries=0, timeout=timeout)
        finally:
            conn.release()
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Worker bootstrap signals (run only inside the worker process, never the API).
# ---------------------------------------------------------------------------
from celery.signals import worker_init  # noqa: E402


@worker_init.connect
def _start_worker_metrics(**_kwargs):
    """Start the Prometheus worker-metrics endpoint once per worker."""
    try:
        import os

        from app.core import worker_metrics

        mp_dir = settings.prometheus_multiproc_dir or os.environ.get(
            "PROMETHEUS_MULTIPROC_DIR"
        )
        if mp_dir:
            worker_metrics._clear_multiproc_dir(mp_dir)
        worker_metrics.start_metrics_server()
    except Exception:  # pragma: no cover - metrics must never block the worker
        pass


# Wire OpenTelemetry into the worker process when enabled.
if settings.otel_enabled:
    try:
        from app.core.telemetry import instrument_celery

        instrument_celery()
    except Exception:  # pragma: no cover - telemetry must never block the worker
        pass
