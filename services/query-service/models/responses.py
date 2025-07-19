"""
Response models for query service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SearchResultChunk(BaseModel):
    """A search result chunk with similarity score"""
    id: str = Field(..., description="Unique identifier for this chunk")
    doctype: str = Field(..., description="Type of the source document")
    docname: str = Field(..., description="Name/ID of the source document")
    field_name: str = Field(..., description="Field name from which content was extracted")
    content: str = Field(..., description="Text content of the chunk")
    score: float = Field(..., description="Similarity score (0-1)")
    
    # Optional metadata (included when include_metadata=True)
    chunk_index: Optional[int] = Field(None, description="Index of this chunk within the document")
    total_chunks: Optional[int] = Field(None, description="Total number of chunks for this document")
    timestamp: Optional[datetime] = Field(None, description="When this chunk was created")
    source_url: Optional[str] = Field(None, description="URL to the source document")
    content_length: Optional[int] = Field(None, description="Length of the chunk content in characters")
    word_count: Optional[int] = Field(None, description="Number of words in the chunk")

    class Config:
        schema_extra = {
            "example": {
                "id": "doc123_field456_chunk1",
                "doctype": "User",
                "docname": "user-001",
                "field_name": "description",
                "content": "User permissions can be configured through the Role Permission Manager...",
                "score": 0.85,
                "chunk_index": 1,
                "total_chunks": 3,
                "timestamp": "2024-01-15T10:30:00Z",
                "source_url": "https://frappe.local/app/user/user-001",
                "content_length": 256,
                "word_count": 42
            }
        }


class SearchResponse(BaseModel):
    """Response model for semantic search"""
    query: str = Field(..., description="The original search query")
    chunks: List[SearchResultChunk] = Field(..., description="List of matching document chunks")
    total_results: int = Field(..., description="Total number of results found")
    processing_time_ms: float = Field(..., description="Time taken to process the query in milliseconds")
    
    # Search metadata
    embedding_time_ms: Optional[float] = Field(None, description="Time taken to generate query embedding")
    search_time_ms: Optional[float] = Field(None, description="Time taken to search vectors")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")
    score_threshold_used: Optional[float] = Field(None, description="Score threshold that was applied")

    class Config:
        schema_extra = {
            "example": {
                "query": "How to configure user permissions?",
                "chunks": [
                    {
                        "id": "doc123_field456_chunk1",
                        "doctype": "User",
                        "docname": "user-001",
                        "field_name": "description",
                        "content": "User permissions can be configured through the Role Permission Manager...",
                        "score": 0.85
                    }
                ],
                "total_results": 1,
                "processing_time_ms": 125.5,
                "embedding_time_ms": 45.2,
                "search_time_ms": 80.3,
                "filters_applied": {"doctype": "User"},
                "score_threshold_used": 0.7
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status (healthy/unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    
    # Service-specific health info
    embedding_service_ready: Optional[bool] = Field(None, description="Whether embedding service is ready")
    vector_db_ready: Optional[bool] = Field(None, description="Whether vector database is ready")
    vector_db_points_count: Optional[int] = Field(None, description="Number of points in vector database")
    cache_size: Optional[int] = Field(None, description="Current cache size")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "embedding_service_ready": True,
                "vector_db_ready": True,
                "vector_db_points_count": 1250,
                "cache_size": 45
            }
        }