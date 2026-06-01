"""Prometheus metrics for the Celery worker.

The worker runs a prefork pool, so each child process increments metrics in its
own memory. To aggregate correctly we run ``prometheus_client`` in
**multiprocess mode** (``PROMETHEUS_MULTIPROC_DIR``): children write metric
values to mmap files and a small HTTP server in the main process exposes the
aggregated registry on ``settings.worker_metrics_port``.

Generic worker signals (active workers, tasks/sec, runtime) are also covered by
the separate ``celery-exporter`` service; the metrics here are the
embedding-pipeline-specific ones (retries, DLQ routing, rate limits, Qdrant
write failures, processing duration).
"""

from __future__ import annotations

import glob
import logging
import os

from prometheus_client import Counter, Histogram

from app.core.config import settings

logger = logging.getLogger("app.worker_metrics")

# --- pipeline counters/histograms (multiprocess-safe: no plain gauges) -----
tasks_received_total = Counter(
    "worker_tasks_received_total", "Tasks received by the worker.", ("task",)
)
tasks_processed_total = Counter(
    "worker_tasks_processed_total",
    "Tasks finished, by terminal status.",
    ("task", "status"),
)
task_retries_total = Counter(
    "worker_task_retries_total",
    "Task retries scheduled, by reason.",
    ("task", "reason"),
)
dead_letter_total = Counter(
    "worker_dead_letter_total",
    "Tasks routed to the dead-letter queue, by reason.",
    ("task", "reason"),
)
task_processing_seconds = Histogram(
    "worker_task_processing_seconds",
    "End-to-end task processing duration (seconds).",
    ("task",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
embedding_requests_total = Counter(
    "worker_embedding_requests_total", "Embedding batch requests issued."
)
embedding_rate_limited_total = Counter(
    "worker_embedding_rate_limited_total", "Embedding calls rejected by rate limits."
)
qdrant_write_failures_total = Counter(
    "worker_qdrant_write_failures_total", "Qdrant upsert failures."
)
chunks_embedded_total = Counter(
    "worker_chunks_embedded_total", "Total document chunks embedded + stored."
)
chat_analytics_consumed_total = Counter(
    "worker_chat_analytics_consumed_total",
    "Chat analytics events consumed from RabbitMQ by the worker.",
)


def _clear_multiproc_dir(mp_dir: str) -> None:
    os.makedirs(mp_dir, exist_ok=True)
    for f in glob.glob(os.path.join(mp_dir, "*.db")):
        try:
            os.remove(f)
        except OSError:
            pass


def start_metrics_server() -> None:
    """Start the worker metrics HTTP endpoint (call once in the main process)."""
    from prometheus_client import CollectorRegistry, start_http_server
    from prometheus_client import multiprocess

    port = settings.worker_metrics_port
    mp_dir = settings.prometheus_multiproc_dir or os.environ.get(
        "PROMETHEUS_MULTIPROC_DIR"
    )

    try:
        if mp_dir:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            start_http_server(port, registry=registry)
        else:
            start_http_server(port)
        logger.info("worker metrics server listening on :%d", port)
    except Exception as exc:  # pragma: no cover - never block worker startup
        logger.warning("could not start worker metrics server: %s", exc)
