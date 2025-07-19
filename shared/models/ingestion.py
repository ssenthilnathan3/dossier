"""
Ingestion-related data models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from .base import JobStatus


class IngestionRequest(BaseModel):
    """Request model for document ingestion"""
    doctype: str = Field(..., description="Type of documents to ingest")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply when fetching documents")
    batch_size: int = Field(default=100, description="Number of documents to process in each batch", alias="batchSize")
    force_update: bool = Field(default=False, description="Whether to force update existing chunks", alias="forceUpdate")

    class Config:
        populate_by_name = True


class IngestionResponse(BaseModel):
    """Response model for ingestion requests"""
    job_id: str = Field(..., description="Unique identifier for the ingestion job", alias="jobId")
    status: JobStatus = Field(..., description="Current status of the job")
    processed: int = Field(default=0, description="Number of documents processed")
    updated: int = Field(default=0, description="Number of chunks updated")
    failed: int = Field(default=0, description="Number of documents that failed processing")
    errors: Optional[List[str]] = Field(None, description="List of error messages")

    class Config:
        populate_by_name = True