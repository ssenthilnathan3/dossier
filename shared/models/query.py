"""
Query-related data models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from .document import DocumentChunk


class QueryRequest(BaseModel):
    """Request model for querying the RAG system"""
    query: str = Field(..., description="The user's query")
    top_k: int = Field(default=5, description="Number of top results to return", alias="topK")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply to the search")
    include_metadata: bool = Field(default=True, description="Whether to include metadata in response", alias="includeMetadata")

    class Config:
        populate_by_name = True


class QueryResponse(BaseModel):
    """Response model for RAG queries"""
    answer: str = Field(..., description="Generated answer to the query")
    sources: List[DocumentChunk] = Field(..., description="Source chunks used to generate the answer")
    confidence: float = Field(..., description="Confidence score of the answer (0-1)")
    processing_time: float = Field(..., description="Time taken to process the query in seconds", alias="processingTime")

    class Config:
        populate_by_name = True