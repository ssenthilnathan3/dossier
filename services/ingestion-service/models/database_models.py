"""
Database models for the ingestion service
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, JSON, Text
from sqlalchemy.sql import func
from database import Base


class DoctypeConfigModel(Base):
    """Database model for doctype configuration"""
    __tablename__ = "doctype_configs"
    
    doctype = Column(String(255), primary_key=True)
    enabled = Column(Boolean, default=True, nullable=False)
    fields = Column(JSON, nullable=False)  # List of field names
    filters = Column(JSON, default=dict)   # Dictionary of filters
    chunk_size = Column(Integer, default=1000, nullable=False)
    chunk_overlap = Column(Integer, default=200, nullable=False)
    last_sync = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IngestionJobModel(Base):
    """Database model for ingestion jobs"""
    __tablename__ = "ingestion_jobs"
    
    job_id = Column(String(255), primary_key=True)
    doctype = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="queued")
    filters = Column(JSON, default=dict)
    batch_size = Column(Integer, default=100)
    processed = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    errors = Column(JSON, default=list)  # List of error messages
    job_metadata = Column(JSON, default=dict)  # Additional processing metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)