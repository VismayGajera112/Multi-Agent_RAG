"""Ingestion error taxonomy.

The worker's retry/DLQ policy hinges on a single distinction:

  * **TransientIngestionError** — the operation might succeed if tried again
    later (Gemini rate limit, Qdrant temporarily unreachable, network blip).
    => retried with exponential back-off + jitter, then dead-lettered only
       after ``max_retries`` is exhausted.

  * **PermanentIngestionError** — retrying will never help (malformed/empty
    PDF, missing file, unsupported content). This is a *poison message*.
    => routed straight to the DLQ, no retries wasted.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for all ingestion failures."""


class TransientIngestionError(IngestionError):
    """Retryable failure (rate limit, network, temporary backend outage)."""


class PermanentIngestionError(IngestionError):
    """Non-retryable failure — a poison message bound for the DLQ."""


# ---- Transient specialisations -------------------------------------------
class EmbeddingRateLimitError(TransientIngestionError):
    """Embedding provider returned a rate-limit / quota error (HTTP 429)."""


class EmbeddingBackendError(TransientIngestionError):
    """Embedding provider failed transiently (5xx, timeout, connection)."""


class QdrantWriteError(TransientIngestionError):
    """Writing vectors to Qdrant failed transiently."""


# ---- Permanent specialisations -------------------------------------------
class MalformedPDFError(PermanentIngestionError):
    """The uploaded file could not be parsed as a PDF, or contained no text."""


class MissingFileError(PermanentIngestionError):
    """The referenced file does not exist on the shared volume."""
