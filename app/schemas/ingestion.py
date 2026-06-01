from typing import Optional

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    """JSON enqueue path — references an already-available file/URI."""

    document_uri: str = Field(
        ..., min_length=1, description="URI/path of the PDF to ingest"
    )
    collection: Optional[str] = Field(
        None, description="Override the target Qdrant collection"
    )
    metadata: Optional[dict] = Field(
        default_factory=dict, description="Arbitrary client metadata"
    )


class UploadAcceptedResponse(BaseModel):
    """Immediate async response for the upload write path."""

    document_id: str
    task_id: str
    status: str = "PENDING"
    queue: str = "pdf_ingestion_queue"
    filename: Optional[str] = None
    size_bytes: int = 0
    uploaded_at: str
    upload_to_queue_ms: float = 0.0
    message: str = "Upload accepted; ingestion task published"


class IngestionAcceptedResponse(BaseModel):
    document_id: str
    task_id: str
    status: str = "PENDING"
    queue: str = "pdf_ingestion_queue"
    message: str = "Ingestion job accepted and queued"


class IngestionStatusResponse(BaseModel):
    document_id: str
    task_id: Optional[str] = None
    status: str  # PENDING | STARTED | RETRY | SUCCESS | FAILURE
    result: Optional[dict] = None
    error: Optional[str] = None
