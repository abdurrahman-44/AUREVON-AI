from typing import List
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Research topic or search query")
    max_sources: int = Field(4, ge=1, le=10)


class SourceCitation(BaseModel):
    title: str
    snippet: str
    url: str


class ResearchResponse(BaseModel):
    query: str
    summary: str
    citations: List[SourceCitation]
    source_count: int
