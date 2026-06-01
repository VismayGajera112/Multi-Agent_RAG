"""PDF parsing + text chunking.

Any failure to read/parse the file, or a PDF that yields no extractable text,
is treated as a **permanent** (poison) error so the worker dead-letters it
instead of retrying forever.
"""

from __future__ import annotations

import logging
import os
from typing import List

from app.core.config import settings
from app.core.ingestion_errors import MalformedPDFError, MissingFileError

logger = logging.getLogger("app.pdf_parser")


def extract_text(file_path: str) -> str:
    """Extract all text from a PDF on the shared volume."""
    if not file_path or not os.path.exists(file_path):
        raise MissingFileError(f"file not found: {file_path}")
    if os.path.getsize(file_path) == 0:
        raise MalformedPDFError(f"file is empty: {file_path}")

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError, PdfStreamError

        reader = PdfReader(file_path)
        parts = [(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, PdfStreamError, ValueError) as exc:
        raise MalformedPDFError(f"could not parse PDF {file_path}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - corrupt files raise many types
        raise MalformedPDFError(f"could not parse PDF {file_path}: {exc}") from exc

    text = "\n".join(parts).strip()
    if not text:
        raise MalformedPDFError(f"no extractable text in PDF: {file_path}")
    return text


def chunk_text(text: str) -> List[str]:
    """Split text into overlapping character windows for embedding."""
    size = settings.chunk_size_chars
    overlap = settings.chunk_overlap_chars
    step = max(1, size - overlap)

    chunks: List[str] = []
    for start in range(0, len(text), step):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if len(chunks) >= settings.max_chunks_per_doc:
            logger.warning(
                "document hit max_chunks_per_doc=%d; truncating",
                settings.max_chunks_per_doc,
            )
            break
    if not chunks:
        raise MalformedPDFError("document produced no usable chunks")
    return chunks
