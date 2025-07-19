"""
Document-related data models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class DocumentMetadata(BaseModel):
    """Metadata for a document chunk"""
    chunk_index: int = Field(..., description="Index of this chunk within the document", alias="chunkIndex")
    total_chunks: int = Field(..., description="Total number of chunks for this document", alias="totalChunks")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this chunk was created")
    source_url: Optional[str] = Field(None, description="URL to the source document", alias="sourceUrl")
    
    # Enhanced metadata fields
    content_length: int = Field(..., description="Length of the chunk content in characters", alias="contentLength")
    word_count: int = Field(..., description="Number of words in the chunk", alias="wordCount")
    sentence_count: int = Field(default=0, description="Number of sentences in the chunk", alias="sentenceCount")
    paragraph_count: int = Field(default=0, description="Number of paragraphs in the chunk", alias="paragraphCount")
    
    # Chunking strategy metadata
    chunking_strategy: str = Field(default="recursive", description="Strategy used for chunking", alias="chunkingStrategy")
    semantic_boundaries: Dict[str, int] = Field(default_factory=dict, description="Semantic boundary counts", alias="semanticBoundaries")
    
    # Quality metrics
    quality_score: Optional[float] = Field(None, description="Quality score of the chunk (0-1)", alias="qualityScore")
    overlap_with_previous: int = Field(default=0, description="Character overlap with previous chunk", alias="overlapWithPrevious")
    overlap_with_next: int = Field(default=0, description="Character overlap with next chunk", alias="overlapWithNext")
    
    # Processing metadata
    processing_time_ms: Optional[float] = Field(None, description="Time taken to process this chunk in milliseconds", alias="processingTimeMs")
    error_count: int = Field(default=0, description="Number of errors encountered during processing", alias="errorCount")
    warnings: List[str] = Field(default_factory=list, description="List of warnings generated during processing")

    class Config:
        populate_by_name = True


class DocumentChunk(BaseModel):
    """A chunk of document content with embedding"""
    id: str = Field(..., description="Unique identifier for this chunk")
    doctype: str = Field(..., description="Type of the source document")
    docname: str = Field(..., description="Name/ID of the source document")
    field_name: str = Field(..., description="Field name from which content was extracted", alias="fieldName")
    content: str = Field(..., description="Text content of the chunk")
    metadata: DocumentMetadata = Field(..., description="Metadata about this chunk")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding of the content")

    class Config:
        populate_by_name = True