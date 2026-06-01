"""Gemini text-generation client for the chat / RAG orchestration path.

Exposes a *synchronous* streaming generator (``stream_generate``) that yields
answer chunks as they are produced. The chat route bridges this into an async
SSE stream off the event loop so token delivery is never blocked.

As with embeddings, a deterministic local fallback is used when no
``GEMINI_API_KEY`` is configured, so the chat API runs end-to-end in dev/CI.

``stats`` is mutated in place with: ``provider``, ``prompt_tokens``,
``completion_tokens`` — used downstream for analytics + token metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Iterator, List

from app.core import metrics
from app.core.config import settings

logger = logging.getLogger("app.llm")


class GenerationError(RuntimeError):
    """Raised when the generation backend fails."""


def _estimate_tokens(text: str) -> int:
    # Rough heuristic (~¾ word/token); only used for the fallback provider.
    return max(1, len(text.split()))


def _fallback_stream(query: str, contexts: List[str], stats: Dict) -> Iterator[str]:
    """Deterministic, context-grounded answer streamed word-by-word."""
    if contexts:
        snippet = " ".join(contexts[0].split()[:60])
        answer = (
            f"Based on {len(contexts)} retrieved passage(s), here is a summary "
            f"relevant to your question \"{query}\": {snippet} "
            "(Set GEMINI_API_KEY to enable full Gemini-generated answers.)"
        )
    else:
        answer = (
            f"I could not find any indexed context for \"{query}\". "
            "Try ingesting relevant documents first."
        )

    stats["provider"] = "fallback"
    stats["prompt_tokens"] = _estimate_tokens(query + " ".join(contexts))
    stats["completion_tokens"] = _estimate_tokens(answer)

    for word in answer.split():
        yield word + " "
        time.sleep(0.01)  # simulate token pacing for a realistic stream
    metrics.gemini_requests_total.labels(operation="chat", outcome="fallback").inc()


def _gemini_stream(prompt: str, stats: Dict) -> Iterator[str]:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_chat_model,
        generation_config={
            "max_output_tokens": settings.chat_max_output_tokens,
            "temperature": settings.chat_temperature,
        },
    )
    stats["provider"] = "gemini"
    try:
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            text = getattr(chunk, "text", "") or ""
            if text:
                yield text
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            stats["prompt_tokens"] = getattr(usage, "prompt_token_count", 0) or 0
            stats["completion_tokens"] = (
                getattr(usage, "candidates_token_count", 0) or 0
            )
        metrics.gemini_requests_total.labels(operation="chat", outcome="success").inc()
    except Exception as exc:  # noqa: BLE001
        metrics.gemini_requests_total.labels(operation="chat", outcome="error").inc()
        logger.error("gemini generation failed: %s", exc)
        raise GenerationError(str(exc)) from exc


def stream_generate(
    query: str, prompt: str, contexts: List[str], stats: Dict
) -> Iterator[str]:
    """Yield answer text chunks for the given prompt (Gemini or fallback)."""
    if settings.gemini_api_key:
        yield from _gemini_stream(prompt, stats)
    else:
        yield from _fallback_stream(query, contexts, stats)
