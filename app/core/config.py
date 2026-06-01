"""Centralised application settings.

Every value is read from the environment (12-factor). Defaults are tuned so
the app runs unchanged inside docker-compose, where service names
(``rabbitmq``, ``redis``, ``qdrant``, ``otel-collector``) resolve over the
shared ``ragnet`` network.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------
    service_name: str = "multi-agent-rag"
    environment: str = "local"

    # Comma-separated list of allowed CORS origins for the frontend ("*" = any).
    cors_allow_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.cors_allow_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # ------------------------------------------------------------------
    # Message broker (RabbitMQ) + result backend / cache (Redis)
    # ------------------------------------------------------------------
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672//"
    redis_url: str = "redis://redis:6379/0"
    # Separate logical DB for the ad-hoc cache / ingestion-state, kept apart
    # from the Celery result backend (db 0) to simplify flushing.
    redis_cache_url: str = "redis://redis:6379/1"

    # ------------------------------------------------------------------
    # Vector store (Qdrant)
    # ------------------------------------------------------------------
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "documents"

    # ------------------------------------------------------------------
    # Embeddings (Gemini) + chunking
    # ------------------------------------------------------------------
    # When no key is set the pipeline falls back to a deterministic local
    # embedding so the system runs end-to-end in dev/CI without credentials.
    gemini_api_key: Optional[str] = None
    # gemini-embedding-001 returns 3072-dim (normalised) vectors by default.
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dim: int = 3072
    embedding_max_batch: int = 16
    # Character-based chunking (cheap + dependency-free).
    chunk_size_chars: int = 2000
    chunk_overlap_chars: int = 200
    max_chunks_per_doc: int = 1000

    # ------------------------------------------------------------------
    # Chat / generation (Gemini) + RAG retrieval
    # ------------------------------------------------------------------
    gemini_chat_model: str = "gemini-2.5-flash"
    chat_top_k: int = 5
    chat_max_output_tokens: int = 1024
    chat_temperature: float = 0.2
    # Async analytics: chat events published here are consumed by the worker.
    chat_analytics_queue: str = "chat_analytics_queue"
    chat_analytics_enabled: bool = True
    chat_analytics_history_max: int = 500

    # ------------------------------------------------------------------
    # Worker Prometheus metrics endpoint (multiprocess-aware)
    # ------------------------------------------------------------------
    worker_metrics_port: int = 9809
    prometheus_multiproc_dir: Optional[str] = None

    # ------------------------------------------------------------------
    # Celery tuning
    # ------------------------------------------------------------------
    celery_task_serializer: str = "json"
    celery_worker_concurrency: int = 4
    celery_task_soft_time_limit: int = 300   # 5 min — raises SoftTimeLimitExceeded
    celery_task_time_limit: int = 360        # 6 min — hard SIGKILL
    # Exponential back-off ceiling + base for transient task failures.
    celery_retry_backoff_base: int = 2       # seconds: 2, 4, 8, 16 ...
    celery_retry_backoff_max: int = 600      # cap the delay at 10 min
    celery_max_retries: int = 5

    # ------------------------------------------------------------------
    # OpenTelemetry (optional — only active when enabled)
    # ------------------------------------------------------------------
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    # "grpc" (4317) or "http/protobuf" (4318)
    otel_exporter_otlp_protocol: str = "grpc"

    # ------------------------------------------------------------------
    # Caching defaults
    # ------------------------------------------------------------------
    cache_ttl_seconds: int = 3600
    ingestion_state_ttl_seconds: int = 86400

    # ------------------------------------------------------------------
    # PDF upload (write path)
    # ------------------------------------------------------------------
    # Shared volume mounted into both the API and the worker so the worker can
    # read the persisted file by path.
    upload_dir: str = "/data/uploads"
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MiB
    # Bounded publish-retry policy applied when the broker is flaky.
    publish_max_retries: int = 3


settings = Settings()
