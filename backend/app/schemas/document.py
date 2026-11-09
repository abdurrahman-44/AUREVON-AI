from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    filename: str
    file_type: str
    file_size_bytes: int
    processing_status: str
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentQueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 4
    min_similarity: Optional[float] = 0.25


class DocumentChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: Optional[int] = None
    content: str
    similarity: float


class DocumentQueryResponse(BaseModel):
    query: str
    results: List[DocumentChunkResult]
    total_found: int
