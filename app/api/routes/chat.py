"""Real-time chat API with Gemini orchestration (RAG).

Design goals (acceptance criteria):
  * The chat path is **fully independent of the Celery worker / queue**: it
    embeds the query, searches Qdrant, and generates the answer inline. If the
    broker is down, chat still works.
  * Analytics events (query, latency, tokens, retrieval hits) are published to
    RabbitMQ **fire-and-forget**, off the streaming hot path, so streaming
    performance is never affected by queue operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.core import metrics, rag
from app.core.config import settings
from app.core.llm import GenerationError, stream_generate
from app.core.redis_client import get_chat_analytics
from app.core.task_publisher import BrokerPublishError, enqueue
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.tasks.analytics_tasks import record_chat_analytics

logger = logging.getLogger("app.chat")
router = APIRouter()

CHAT_ANALYTICS_QUEUE = settings.chat_analytics_queue

# Keep references to fire-and-forget analytics tasks so they aren't GC'd.
_bg_tasks: set[asyncio.Task] = set()


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _publish_analytics_sync(event: dict) -> None:
    """Publish one analytics event to RabbitMQ (best-effort, never raises up)."""
    try:
        enqueue(
            record_chat_analytics,
            queue=CHAT_ANALYTICS_QUEUE,
            kwargs={"event": event},
            correlation_id=event.get("session_id"),
        )
        metrics.chat_analytics_published_total.labels(outcome="success").inc()
    except BrokerPublishError as exc:
        # Broker down must NOT break chat — just record + log and move on.
        metrics.chat_analytics_published_total.labels(outcome="failure").inc()
        logger.warning("chat analytics publish failed (non-fatal): %s", exc)


def _schedule_analytics(event: dict) -> None:
    """Schedule analytics publishing without blocking the response."""
    if not settings.chat_analytics_enabled:
        return
    task = asyncio.create_task(run_in_threadpool(_publish_analytics_sync, event))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def _build_event(req: ChatRequest, session_id: str, mode: str, stats: dict,
                 hits: int, latency_ms: float) -> dict:
    pt = int(stats.get("prompt_tokens", 0))
    ct = int(stats.get("completion_tokens", 0))
    return {
        "event": "chat_completed",
        "session_id": session_id,
        "query": req.query,
        "mode": mode,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "retrieval_hits": hits,
        "provider": stats.get("provider"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _bridge(sync_gen_factory: Callable[[], Iterator[str]]):
    """Run a blocking sync generator in a thread, yielding chunks async."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()
    holder: dict = {}

    def producer() -> None:
        try:
            for chunk in sync_gen_factory():
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:  # noqa: BLE001 - surfaced to the consumer
            holder["error"] = exc
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    fut = loop.run_in_executor(None, producer)
    while True:
        item = await queue.get()
        if item is sentinel:
            break
        yield item
    await fut
    if "error" in holder:
        raise holder["error"]


async def _retrieve(req: ChatRequest):
    """Retrieve context, mapping failures to clean HTTP errors."""
    try:
        hits = await run_in_threadpool(
            rag.retrieve, req.query, req.top_k, req.collection
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("retrieval failed: %s", exc)
        raise HTTPException(status_code=503, detail="Retrieval backend unavailable.")
    metrics.chat_retrieval_hits.observe(len(hits))
    return hits


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """Stream a RAG answer token-by-token via Server-Sent Events."""
    session_id = req.session_id or str(uuid.uuid4())
    start = time.perf_counter()

    hits = await _retrieve(req)
    prompt = rag.build_prompt(req.query, hits)
    contexts = [h["text"] for h in hits]
    sources = [
        {**h, "text": (h["text"][:300] + ("…" if len(h["text"]) > 300 else ""))}
        for h in hits
    ]

    async def event_gen():
        metrics.chat_active_streams.inc()
        stats: dict = {}
        answer_parts: list[str] = []
        first = False
        try:
            yield _sse({"type": "sources", "session_id": session_id, "sources": sources})

            def factory():
                return stream_generate(req.query, prompt, contexts, stats)

            async for chunk in _bridge(factory):
                if not first:
                    metrics.chat_time_to_first_token_seconds.observe(
                        time.perf_counter() - start
                    )
                    first = True
                answer_parts.append(chunk)
                yield _sse({"type": "token", "text": chunk})

            latency_ms = (time.perf_counter() - start) * 1000
            pt = int(stats.get("prompt_tokens", 0))
            ct = int(stats.get("completion_tokens", 0))
            metrics.chat_tokens_total.labels(kind="prompt").inc(pt)
            metrics.chat_tokens_total.labels(kind="completion").inc(ct)
            metrics.chat_request_latency_seconds.labels(mode="stream").observe(
                latency_ms / 1000
            )
            metrics.chat_requests_total.labels(mode="stream", status="success").inc()

            # Fire-and-forget analytics — off the hot path, never blocks tokens.
            _schedule_analytics(
                _build_event(req, session_id, "stream", stats, len(hits), latency_ms)
            )
            logger.info(
                "chat stream done session_id=%s hits=%d tokens=%d latency_ms=%.1f provider=%s",
                session_id, len(hits), pt + ct, latency_ms, stats.get("provider"),
            )
            yield _sse(
                {
                    "type": "done",
                    "session_id": session_id,
                    "latency_ms": round(latency_ms, 2),
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "retrieval_hits": len(hits),
                    "provider": stats.get("provider"),
                }
            )
        except GenerationError:
            metrics.chat_requests_total.labels(mode="stream", status="error").inc()
            yield _sse({"type": "error", "detail": "Generation backend failed."})
        except Exception as exc:  # noqa: BLE001
            metrics.chat_requests_total.labels(mode="stream", status="error").inc()
            logger.exception("chat stream error: %s", exc)
            yield _sse({"type": "error", "detail": "Internal error during streaming."})
        finally:
            metrics.chat_active_streams.dec()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Non-streaming RAG answer (single JSON response)."""
    session_id = req.session_id or str(uuid.uuid4())
    start = time.perf_counter()

    hits = await _retrieve(req)
    prompt = rag.build_prompt(req.query, hits)
    contexts = [h["text"] for h in hits]

    metrics.chat_active_streams.inc()
    stats: dict = {}
    try:
        def _collect() -> str:
            return "".join(stream_generate(req.query, prompt, contexts, stats))

        answer = await run_in_threadpool(_collect)
    except GenerationError as exc:
        metrics.chat_requests_total.labels(mode="json", status="error").inc()
        raise HTTPException(status_code=502, detail="Generation backend failed.") from exc
    finally:
        metrics.chat_active_streams.dec()

    latency_ms = (time.perf_counter() - start) * 1000
    pt = int(stats.get("prompt_tokens", 0))
    ct = int(stats.get("completion_tokens", 0))
    metrics.chat_tokens_total.labels(kind="prompt").inc(pt)
    metrics.chat_tokens_total.labels(kind="completion").inc(ct)
    metrics.chat_request_latency_seconds.labels(mode="json").observe(latency_ms / 1000)
    metrics.chat_requests_total.labels(mode="json", status="success").inc()

    _schedule_analytics(
        _build_event(req, session_id, "json", stats, len(hits), latency_ms)
    )

    return ChatResponse(
        session_id=session_id,
        answer=answer.strip(),
        sources=[ChatSource(**h) for h in hits],
        retrieval_hits=len(hits),
        prompt_tokens=pt,
        completion_tokens=ct,
        latency_ms=round(latency_ms, 2),
        provider=stats.get("provider", "unknown"),
    )


@router.get("/analytics/recent")
async def recent_analytics(limit: int = 20):
    """Inspect the most recent analytics events consumed off the queue."""
    return {"events": get_chat_analytics(limit=limit)}
