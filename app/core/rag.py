"""Retrieval-augmented generation helpers.

Pure retrieval + prompt assembly — deliberately decoupled from the worker /
Celery so the chat API can answer entirely on its own (embed the query, search
Qdrant, build a grounded prompt). The actual generation lives in ``llm.py``.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.core import metrics
from app.core.config import settings
from app.core.embeddings import embed_query

logger = logging.getLogger("app.rag")


def retrieve(query: str, top_k: Optional[int] = None, collection: Optional[str] = None) -> List[Dict]:
    """Embed ``query`` and return the top-k matching chunks from Qdrant."""
    from app.core.qdrant_client import get_client

    k = top_k or settings.chat_top_k
    coll = collection or settings.qdrant_collection

    try:
        vector = embed_query(query)
        metrics.gemini_requests_total.labels(
            operation="embedding", outcome="success"
        ).inc()
    except Exception:
        metrics.gemini_requests_total.labels(
            operation="embedding", outcome="error"
        ).inc()
        raise

    result = get_client().query_points(
        collection_name=coll,
        query=vector,
        limit=k,
        with_payload=True,
    )

    hits: List[Dict] = []
    for point in result.points:
        payload = point.payload or {}
        hits.append(
            {
                "id": str(point.id),
                "score": round(float(point.score), 4),
                "document_id": payload.get("document_id"),
                "chunk_index": payload.get("chunk_index"),
                "text": payload.get("text", ""),
            }
        )
    return hits


def build_prompt(query: str, hits: List[Dict]) -> str:
    """Assemble a grounded prompt from retrieved context."""
    if hits:
        context_blocks = "\n\n".join(
            f"[{i + 1}] {h['text']}" for i, h in enumerate(hits)
        )
    else:
        context_blocks = "(no relevant context found)"

    return (
        "You are a helpful assistant. Answer the question using ONLY the context "
        "below. If the context is insufficient, say so.\n\n"
        f"Context:\n{context_blocks}\n\n"
        f"Question: {query}\n\nAnswer:"
    )
