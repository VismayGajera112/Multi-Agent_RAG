import asyncio
import contextlib
import logging
import time

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import chat, health, ingestion, tasks
from app.core import metrics
from app.core.celery_app import queue_backlog
from app.core.config import settings
from app.core.telemetry import instrument_fastapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")

BACKLOG_SAMPLE_INTERVAL = 15  # seconds
MONITORED_QUEUES = (
    "pdf_ingestion_queue",
    "chat_analytics_queue",
    "dead_letter_queue",
    "embedding_retry_queue",
)


async def _backlog_sampler() -> None:
    """Periodically refresh the rag_queue_backlog gauge from the broker."""
    while True:
        for q in MONITORED_QUEUES:
            depth = await run_in_threadpool(queue_backlog, q)
            if depth is not None:
                metrics.queue_backlog.labels(queue=q).set(depth)
        await asyncio.sleep(BACKLOG_SAMPLE_INTERVAL)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the background queue-backlog sampler."""
    sampler = asyncio.create_task(_backlog_sampler())
    logger.info("Multi-Agent RAG API started (env=%s)", settings.environment)
    try:
        yield
    finally:
        sampler.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sampler


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi-Agent RAG API",
        version="0.1.0",
        description="Async document ingestion + retrieval orchestration "
        "(Celery + RabbitMQ + Redis + Qdrant).",
        lifespan=lifespan,
    )

    app.add_middleware(LoggingMiddleware)

    # CORS — allow the React frontend (Vite dev server / static build) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])
    app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])

    # Prometheus /metrics endpoint — scraped by the prometheus service.
    Instrumentator(
        should_group_status_codes=True,
        excluded_handlers=["/metrics", "/health.*"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # Make the publish metrics visible (at 0) before the first ingestion.
    metrics.preinitialize(
        task="app.tasks.ingestion_tasks.ingest_pdf", queue="pdf_ingestion_queue"
    )
    metrics.preinitialize_chat()

    # Optional distributed tracing -> OpenTelemetry Collector.
    instrument_fastapi(app)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please retry."},
        )

    return app


app = create_app()
