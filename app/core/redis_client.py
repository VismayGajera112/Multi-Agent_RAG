"""Redis helpers for the caching layer and temporary ingestion state.

The Celery *result backend* uses Redis db 0 (configured in celery_app). This
module uses db 1 (``redis_cache_url``) for application-level caching and for
tracking the lifecycle of an ingestion job while it moves through the queues.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis

from app.core.config import settings

_pool: Optional[redis.ConnectionPool] = None


def get_client() -> redis.Redis:
    """Return a process-wide pooled Redis client for the cache DB."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_cache_url, decode_responses=True
        )
    return redis.Redis(connection_pool=_pool)


# ---------------------------------------------------------------------------
# Generic cache helpers
# ---------------------------------------------------------------------------
def cache_get(key: str) -> Optional[Any]:
    raw = get_client().get(key)
    return json.loads(raw) if raw is not None else None


def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    get_client().set(
        key,
        json.dumps(value),
        ex=ttl if ttl is not None else settings.cache_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Ingestion-state helpers (short-lived job tracking)
# ---------------------------------------------------------------------------
def _state_key(job_id: str) -> str:
    return f"ingestion:state:{job_id}"


def set_ingestion_state(job_id: str, state: dict) -> None:
    get_client().set(
        _state_key(job_id),
        json.dumps(state),
        ex=settings.ingestion_state_ttl_seconds,
    )


def get_ingestion_state(job_id: str) -> Optional[dict]:
    raw = get_client().get(_state_key(job_id))
    return json.loads(raw) if raw is not None else None


# ---------------------------------------------------------------------------
# Chat analytics history (capped list consumed off the analytics queue)
# ---------------------------------------------------------------------------
CHAT_ANALYTICS_KEY = "chat:analytics:events"


def push_chat_analytics(event: dict, max_len: int = 500) -> None:
    """Append a chat analytics event to a capped Redis list (newest first)."""
    client = get_client()
    pipe = client.pipeline()
    pipe.lpush(CHAT_ANALYTICS_KEY, json.dumps(event))
    pipe.ltrim(CHAT_ANALYTICS_KEY, 0, max_len - 1)
    pipe.execute()


def get_chat_analytics(limit: int = 50) -> list:
    raw = get_client().lrange(CHAT_ANALYTICS_KEY, 0, limit - 1)
    return [json.loads(r) for r in raw]
