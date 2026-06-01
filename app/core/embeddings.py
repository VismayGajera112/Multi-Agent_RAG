"""Embedding client.

Primary backend is Google **Gemini** (``models/text-embedding-004`` -> 768-dim).
If no ``GEMINI_API_KEY`` is configured the module falls back to a deterministic
local embedding so the whole ingestion pipeline (parse -> embed -> upsert) can
run end-to-end in dev/CI without credentials. The fallback is clearly logged.

Provider errors are normalised into the ingestion error taxonomy so the worker
can apply the right retry/DLQ policy:

    rate limit / quota (429)         -> EmbeddingRateLimitError  (transient)
    5xx / timeout / connection       -> EmbeddingBackendError    (transient)
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import List

from app.core.config import settings
from app.core.ingestion_errors import (
    EmbeddingBackendError,
    EmbeddingRateLimitError,
)

logger = logging.getLogger("app.embeddings")


@lru_cache(maxsize=1)
def _use_gemini() -> bool:
    if settings.gemini_api_key:
        return True
    logger.warning(
        "GEMINI_API_KEY not set — using deterministic local embeddings "
        "(dim=%d). Set GEMINI_API_KEY to enable real Gemini embeddings.",
        settings.embedding_dim,
    )
    return False


def _fallback_embedding(text: str) -> List[float]:
    """Deterministic, normalised pseudo-embedding derived from the text hash.

    Not semantically meaningful — purely so the pipeline produces stable,
    correctly-shaped vectors without external calls.
    """
    import numpy as np

    seed = int.from_bytes(
        hashlib.sha256(text.encode("utf-8")).digest()[:8], "little", signed=False
    )
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(settings.embedding_dim).astype("float32")
    norm = float(np.linalg.norm(vec)) or 1.0
    return (vec / norm).tolist()


def _embed_gemini(texts: List[str], task_type: str) -> List[List[float]]:
    import google.generativeai as genai
    from google.api_core import exceptions as gexc

    genai.configure(api_key=settings.gemini_api_key)
    try:
        resp = genai.embed_content(
            model=settings.embedding_model,
            content=texts,
            task_type=task_type,
        )
    except (gexc.ResourceExhausted, gexc.TooManyRequests) as exc:
        raise EmbeddingRateLimitError(str(exc)) from exc
    except (
        gexc.ServiceUnavailable,
        gexc.DeadlineExceeded,
        gexc.InternalServerError,
        gexc.GatewayTimeout,
        gexc.Aborted,
        ConnectionError,
        TimeoutError,
    ) as exc:
        raise EmbeddingBackendError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - normalise anything else to transient
        raise EmbeddingBackendError(f"embedding call failed: {exc}") from exc

    embedding = resp["embedding"]
    # google-generativeai returns a single vector for a str, list of vectors
    # for a list. Normalise to list-of-vectors.
    if embedding and isinstance(embedding[0], (int, float)):
        return [embedding]  # type: ignore[list-item]
    return embedding


def embed_texts(
    texts: List[str], task_type: str = "retrieval_document"
) -> List[List[float]]:
    """Embed a batch of texts, returning one vector per input (in order)."""
    if not texts:
        return []

    if not _use_gemini():
        return [_fallback_embedding(t) for t in texts]

    vectors: List[List[float]] = []
    batch = settings.embedding_max_batch
    for i in range(0, len(texts), batch):
        vectors.extend(_embed_gemini(texts[i : i + batch], task_type))
    return vectors


def embed_query(text: str) -> List[float]:
    """Embed a single search query (uses the retrieval_query task type)."""
    return embed_texts([text], task_type="retrieval_query")[0]
