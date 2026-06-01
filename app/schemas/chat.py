"""Chat API request/response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question.")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Context chunks to retrieve.")
    collection: Optional[str] = Field(None, description="Override the Qdrant collection.")
    session_id: Optional[str] = Field(None, description="Client conversation id (analytics).")


class ChatSource(BaseModel):
    id: str
    score: float
    document_id: Optional[str] = None
    chunk_index: Optional[int] = None
    text: str


class ChatResponse(BaseModel):
    session_id: Optional[str] = None
    answer: str
    sources: List[ChatSource]
    retrieval_hits: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    provider: str
