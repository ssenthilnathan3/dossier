"""
Request models for the embedding service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class EmbeddingRequest(BaseModel):
    """Request for generating a single embedding"""
    text: str = Field(..., description="Text to generate embedding for", min_length=1)
    use_cache: bool = Field(default=True, description="Whether to use cached embeddings")


class BatchEmbeddingRequest(BaseModel):
    """Request for generating multiple embeddings"""
    texts: List[str] = Field(..., description="List of texts to generate embeddings for", min_items=1)
    batch_size: Optional[int] = Field(default=32, description="Batch size for processing", ge=1, le=128)
    use_cache: bool = Field(default=True, description="Whether to use cached embeddings")


class VectorUpsertRequest(BaseModel):
    """Request for upserting vectors to Qdrant"""
    id: str = Field(..., description="Unique identifier for the vector")
    vector: List[float] = Field(..., description="Vector embedding")
    payload: Dict[str, Any] = Field(..., description="Metadata payload")


class BatchVectorUpsertRequest(BaseModel):
    """Request for upserting multiple vectors to Qdrant"""
    vectors: List[VectorUpsertRequest] = Field(..., description="List of vectors to upsert", min_items=1)
    batch_size: Optional[int] = Field(default=100, description="Batch size for processing", ge=1, le=1000)


class VectorSearchRequest(BaseModel):
    """Request for searching vectors in Qdrant"""
    query_vector: List[float] = Field(..., description="Query vector for similarity search")
    limit: Optional[int] = Field(default=10, description="Maximum number of results", ge=1, le=100)
    score_threshold: Optional[float] = Field(default=None, description="Minimum similarity score", ge=0.0, le=1.0)
    filter_conditions: Optional[Dict[str, Any]] = Field(default=None, description="Filter conditions for search")


class VectorDeleteRequest(BaseModel):
    """Request for deleting vectors from Qdrant"""
    vector_ids: Optional[List[str]] = Field(default=None, description="List of vector IDs to delete")
    filter_conditions: Optional[Dict[str, Any]] = Field(default=None, description="Filter conditions for deletion")