"""
Request models for LLM service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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


class LLMRequest(BaseModel):
    """Request model for LLM generation"""
    query: str = Field(..., description="The user's query")
    context_chunks: List[DocumentChunk] = Field(
        default_factory=list, 
        description="Retrieved document chunks for context",
        alias="contextChunks"
    )
    model: Optional[str] = Field(None, description="Specific model to use (optional)")
    temperature: float = Field(default=0.7, description="Temperature for generation (0-1)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", alias="maxTokens")
    
    class Config:
        populate_by_name = True


class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str = Field(..., description="Role of the message sender (user, assistant, system)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    """Request model for chat completion"""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    context_chunks: List[DocumentChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for context",
        alias="contextChunks"
    )
    model: Optional[str] = Field(None, description="Specific model to use (optional)")
    temperature: float = Field(default=0.7, description="Temperature for generation (0-1)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", alias="maxTokens")
    
    class Config:
        populate_by_name = True


class StreamingRequest(BaseModel):
    """Request model for streaming LLM generation"""
    query: str = Field(..., description="The user's query")
    context_chunks: List[DocumentChunk] = Field(
        default_factory=list, 
        description="Retrieved document chunks for context",
        alias="contextChunks"
    )
    model: Optional[str] = Field(None, description="Specific model to use (optional)")
    temperature: float = Field(default=0.7, description="Temperature for generation (0-1)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", alias="maxTokens")
    
    class Config:
        populate_by_name = True


class StreamingChatRequest(BaseModel):
    """Request model for streaming chat completion"""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    context_chunks: List[DocumentChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for context",
        alias="contextChunks"
    )
    model: Optional[str] = Field(None, description="Specific model to use (optional)")
    temperature: float = Field(default=0.7, description="Temperature for generation (0-1)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", alias="maxTokens")
    
    class Config:
        populate_by_name = True