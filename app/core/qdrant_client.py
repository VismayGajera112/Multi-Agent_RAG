"""Qdrant vector-store connection helper.

Lazily constructs a singleton client so importing this module never forces a
network connection at process start (keeps FastAPI/worker boot fast and
resilient to Qdrant not being ready yet).
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from app.core.config import settings
from app.core.ingestion_errors import QdrantWriteError

_client = None


def get_client():
    """Return a shared QdrantClient pointed at ``settings.qdrant_url``."""
    global _client
    if _client is None:
        from qdrant_client import QdrantClient

        _client = QdrantClient(url=settings.qdrant_url, prefer_grpc=False)
    return _client


def ensure_collection(vector_size: int = 768, distance: str = "Cosine") -> None:
    """Create the configured collection if it does not already exist."""
    from qdrant_client.models import Distance, VectorParams

    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=vector_size, distance=Distance[distance.upper()]
            ),
        )


def upsert_chunks(
    document_id: str,
    chunks: List[str],
    vectors: List[List[float]],
    *,
    collection: Optional[str] = None,
    extra_payload: Optional[dict] = None,
) -> int:
    """Upsert chunk vectors for a document. Returns the number of points written.

    Transient Qdrant/network failures are raised as ``QdrantWriteError`` so the
    worker retries them; the collection is created on first use.
    """
    from qdrant_client.models import PointStruct

    coll = collection or settings.qdrant_collection
    try:
        ensure_collection(vector_size=settings.embedding_dim)
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{i}")),
                vector=vector,
                payload={
                    "document_id": document_id,
                    "chunk_index": i,
                    "text": chunk,
                    **(extra_payload or {}),
                },
            )
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        get_client().upsert(collection_name=coll, points=points, wait=True)
        return len(points)
    except Exception as exc:  # noqa: BLE001 - normalise to a retryable error
        raise QdrantWriteError(f"qdrant upsert failed: {exc}") from exc


def healthcheck() -> bool:
    """Best-effort readiness probe used by the API ``/health`` endpoint."""
    try:
        get_client().get_collections()
        return True
    except Exception:
        return False
