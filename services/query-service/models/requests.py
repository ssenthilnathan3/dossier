"""
Request models for query service
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class SearchRequest(BaseModel):
    """Request model for semantic search"""
    query: str = Field(..., description="The search query")
    top_k: int = Field(default=5, description="Number of top results to return", ge=1, le=100)
    score_threshold: Optional[float] = Field(
        default=None, 
        description="Minimum similarity score threshold (0-1)",
        ge=0.0,
        le=1.0
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Filters to apply to the search"
    )
    include_metadata: bool = Field(
        default=True, 
        description="Whether to include detailed metadata in response"
    )

    class Config:
        schema_extra = {
            "example": {
                "query": "How to configure user permissions?",
                "top_k": 5,
                "score_threshold": 0.7,
                "filters": {
                    "doctype": "User"
                },
                "include_metadata": True
            }
        }