"""
Configuration data models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class DoctypeConfig(BaseModel):
    """Configuration for a specific doctype"""
    doctype: str = Field(..., description="Name of the doctype")
    enabled: bool = Field(default=True, description="Whether this doctype is enabled for processing")
    fields: List[str] = Field(..., description="List of fields to extract content from")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filters to apply when fetching documents")
    chunk_size: int = Field(default=1000, description="Size of text chunks for embedding", alias="chunkSize")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks", alias="chunkOverlap")
    last_sync: Optional[datetime] = Field(None, description="Last synchronization timestamp", alias="lastSync")

    class Config:
        populate_by_name = True