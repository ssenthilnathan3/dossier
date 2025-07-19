"""
Response models for the embedding service
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any


class EmbeddingResponse(BaseModel):
    """Response for single embedding generation"""
    embedding: List[float] = Field(..., description="Generated embedding vector")
    dimension: int = Field(..., description="Dimension of the embedding vector")
    model: str = Field(..., description="Model used for embedding generation")


class BatchEmbeddingResponse(BaseModel):
    """Response for batch embedding generation"""
    embeddings: List[List[float]] = Field(..., description="List of generated embedding vectors")
    count: int = Field(..., description="Number of embeddings generated")
    dimension: int = Field(..., description="Dimension of each embedding vector")
    model: str = Field(..., description="Model used for embedding generation")


class VectorSearchResult(BaseModel):
    """Single vector search result"""
    id: str = Field(..., description="Vector ID")
    score: float = Field(..., description="Similarity score")
    payload: Dict[str, Any] = Field(..., description="Vector metadata")


class VectorSearchResponse(BaseModel):
    """Response for vector search"""
    results: List[VectorSearchResult] = Field(..., description="Search results")
    count: int = Field(..., description="Number of results returned")
    query_time_ms: float = Field(..., description="Query execution time in milliseconds")


class VectorUpsertResponse(BaseModel):
    """Response for vector upsert operation"""
    success: bool = Field(..., description="Whether the operation was successful")
    upserted_count: int = Field(..., description="Number of vectors upserted")
    operation_time_ms: float = Field(..., description="Operation execution time in milliseconds")


class VectorDeleteResponse(BaseModel):
    """Response for vector delete operation"""
    success: bool = Field(..., description="Whether the operation was successful")
    deleted_count: int = Field(..., description="Number of vectors deleted")
    operation_time_ms: float = Field(..., description="Operation execution time in milliseconds")


class QdrantHealthResponse(BaseModel):
    """Qdrant health check response"""
    status: str = Field(..., description="Qdrant service status")
    collection: str = Field(..., description="Collection name")
    points_count: int = Field(..., description="Number of points in collection")
    response_time_ms: float = Field(..., description="Response time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether the embedding model is loaded")
    cache_size: int = Field(..., description="Number of cached embeddings")
    qdrant: QdrantHealthResponse = Field(..., description="Qdrant service health")