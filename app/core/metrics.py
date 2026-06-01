"""Application-level Prometheus metrics for task publishing.

These are registered on the default ``prometheus_client`` registry, which is
exactly the registry that ``prometheus-fastapi-instrumentator`` serves on
``/metrics`` — so every metric defined here is scraped by the ``fastapi`` job
without any extra Prometheus config.

Exposed series
--------------
    rag_task_enqueued_total{task,queue}              counter
    rag_task_publish_failures_total{task,queue,error_type}  counter
    rag_task_publish_latency_seconds{task,queue}     histogram
    rag_task_publish_inflight{task,queue}            gauge
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Number of tasks successfully published to the broker.
task_enqueued_total = Counter(
    "rag_task_enqueued_total",
    "Total number of tasks successfully published to the broker.",
    labelnames=("task", "queue"),
)

# Number of publish attempts that failed (broker unreachable, timeout, ...).
task_publish_failures_total = Counter(
    "rag_task_publish_failures_total",
    "Total number of failed task publish attempts.",
    labelnames=("task", "queue", "error_type"),
)

# Wall-clock time spent publishing a task to the broker.
task_publish_latency_seconds = Histogram(
    "rag_task_publish_latency_seconds",
    "Latency of publishing a task to the broker (seconds).",
    labelnames=("task", "queue"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# In-flight publish operations (useful to spot broker back-pressure/hangs).
task_publish_inflight = Gauge(
    "rag_task_publish_inflight",
    "Number of task-publish operations currently in flight.",
    labelnames=("task", "queue"),
)

# End-to-end time from receiving an upload to the task being on the queue.
upload_to_queue_duration_seconds = Histogram(
    "rag_upload_to_queue_duration_seconds",
    "Time from receiving an upload request to the task being enqueued (seconds).",
    labelnames=("queue",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Number of uploaded documents accepted by the write path.
uploads_accepted_total = Counter(
    "rag_uploads_accepted_total",
    "Total number of uploaded documents accepted for ingestion.",
    labelnames=("queue",),
)

# Number of uploads rejected by validation (bad type, too large, empty, ...).
uploads_rejected_total = Counter(
    "rag_uploads_rejected_total",
    "Total number of uploads rejected by validation.",
    labelnames=("reason",),
)

# Current queue backlog (messages ready) sampled from the broker.
queue_backlog = Gauge(
    "rag_queue_backlog",
    "Current number of ready (unconsumed) messages in a queue.",
    labelnames=("queue",),
)

# ---------------------------------------------------------------------------
# Real-time chat / Gemini orchestration metrics
# ---------------------------------------------------------------------------
# Concurrent in-flight chat streams (the headline real-time signal).
chat_active_streams = Gauge(
    "rag_chat_active_streams",
    "Number of chat responses currently being generated/streamed.",
)

# Chat requests handled, by transport (stream|json) and outcome.
chat_requests_total = Counter(
    "rag_chat_requests_total",
    "Total chat requests handled.",
    labelnames=("mode", "status"),
)

# End-to-end chat latency (retrieve + generate), seconds.
chat_request_latency_seconds = Histogram(
    "rag_chat_request_latency_seconds",
    "End-to-end chat latency from request to final token (seconds).",
    labelnames=("mode",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

# Time-to-first-token — the key perceived-latency metric for streaming.
chat_time_to_first_token_seconds = Histogram(
    "rag_chat_time_to_first_token_seconds",
    "Latency from request to the first streamed token (seconds).",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Tokens processed, split into prompt vs completion.
chat_tokens_total = Counter(
    "rag_chat_tokens_total",
    "Total tokens processed by chat, by kind.",
    labelnames=("kind",),
)

# Retrieval hits returned from Qdrant per chat request.
chat_retrieval_hits = Histogram(
    "rag_chat_retrieval_hits",
    "Number of retrieved context chunks per chat request.",
    buckets=(0, 1, 2, 3, 5, 8, 13, 21),
)

# Gemini request throughput, by operation (chat|embedding) and outcome.
gemini_requests_total = Counter(
    "rag_gemini_requests_total",
    "Gemini API requests, by operation and outcome.",
    labelnames=("operation", "outcome"),
)

# Async analytics events published to RabbitMQ from the chat path.
chat_analytics_published_total = Counter(
    "rag_chat_analytics_published_total",
    "Chat analytics events published to RabbitMQ, by outcome.",
    labelnames=("outcome",),
)


def preinitialize(task: str, queue: str) -> None:
    """Touch every label combo so the series appear (at 0) before first use.

    Without this, counters/histograms with labels are invisible to Prometheus
    until the first event, which makes dashboards look empty on a fresh boot.
    """
    task_enqueued_total.labels(task=task, queue=queue)
    task_publish_latency_seconds.labels(task=task, queue=queue)
    task_publish_inflight.labels(task=task, queue=queue).set(0)
    upload_to_queue_duration_seconds.labels(queue=queue)
    uploads_accepted_total.labels(queue=queue)
    queue_backlog.labels(queue=queue).set(0)
    # error_type is open-ended; pre-seed the common broker-down case.
    task_publish_failures_total.labels(
        task=task, queue=queue, error_type="OperationalError"
    )


def preinitialize_chat() -> None:
    """Touch chat metric label combos so they appear (at 0) on a fresh boot."""
    chat_active_streams.set(0)
    for mode in ("stream", "json"):
        chat_requests_total.labels(mode=mode, status="success")
        chat_request_latency_seconds.labels(mode=mode)
    for kind in ("prompt", "completion"):
        chat_tokens_total.labels(kind=kind)
    for operation in ("chat", "embedding"):
        for outcome in ("success", "error", "fallback"):
            gemini_requests_total.labels(operation=operation, outcome=outcome)
    for outcome in ("success", "failure"):
        chat_analytics_published_total.labels(outcome=outcome)
