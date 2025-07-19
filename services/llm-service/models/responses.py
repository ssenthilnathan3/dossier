"""
Response models for LLM service
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import sys
import os

# Add shared models to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
try:
    from models.document import DocumentChunk
except ImportError:
    # Fallback for testing
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from shared.models.document import DocumentChunk


class LLMResponse(BaseModel):
    """Response model for LLM generation"""
    answer: str = Field(..., description="Generated answer")
    sources: List[DocumentChunk] = Field(..., description="Source chunks used for generation")
    model_used: str = Field(..., description="Model that was used for generation", alias="modelUsed")
    processing_time: float = Field(..., description="Processing time in seconds", alias="processingTime")
    token_count: Optional[int] = Field(None, description="Number of tokens generated", alias="tokenCount")
    
    class Config:
        populate_by_name = True


class ChatResponse(BaseModel):
    """Response model for chat completion"""
    message: str = Field(..., description="Generated chat message")
    sources: List[DocumentChunk] = Field(..., description="Source chunks used for generation")
    model_used: str = Field(..., description="Model that was used for generation", alias="modelUsed")
    processing_time: float = Field(..., description="Processing time in seconds", alias="processingTime")
    token_count: Optional[int] = Field(None, description="Number of tokens generated", alias="tokenCount")
    
    class Config:
        populate_by_name = True


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Health status message")


class GenerationResult(BaseModel):
    """Internal result model for generation operations"""
    answer: str = Field(..., description="Generated answer")
    sources: List[DocumentChunk] = Field(..., description="Source chunks used")
    model_used: str = Field(..., description="Model used for generation", alias="modelUsed")
    token_count: Optional[int] = Field(None, description="Token count", alias="tokenCount")
    
    class Config:
        populate_by_name = True


class ChatResult(BaseModel):
    """Internal result model for chat operations"""
    message: str = Field(..., description="Generated message")
    sources: List[DocumentChunk] = Field(..., description="Source chunks used")
    model_used: str = Field(..., description="Model used for generation", alias="modelUsed")
    token_count: Optional[int] = Field(None, description="Token count", alias="tokenCount")
    
    class Config:
        populate_by_name = True