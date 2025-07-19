"""
Base Pydantic models and utilities
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ActionType(str, Enum):
    """Enum for webhook actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class JobStatus(str, Enum):
    """Enum for job statuses"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"