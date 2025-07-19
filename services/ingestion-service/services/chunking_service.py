"""
Intelligent text chunking service with semantic boundary detection
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

# Import shared models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from shared.models.document import DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)


class ChunkingConfig(BaseModel):
    """Configuration for text chunking"""
    chunk_size: int = Field(default=1000, description="Maximum size of each chunk in characters")
    chunk_overlap: int = Field(default=200, description="Number of characters to overlap between chunks")
    separators: List[str] = Field(
        default=[
            # Paragraph boundaries (highest priority for semantic integrity)
            "\n\n\n",  # Multiple line breaks
            "\n\n",    # Double line breaks (paragraph separators)
            # Sentence boundaries
            ". ",      # Period followed by space
            "! ",      # Exclamation followed by space
            "? ",      # Question mark followed by space
            # Clause boundaries
            "; ",      # Semicolon
            ": ",      # Colon
            ", ",      # Comma (for lists and clauses)
            # Line boundaries
            "\n",      # Single line break
            # Word boundaries (lowest priority)
            " ",       # Space between words
            "",        # Character-level split (last resort)
        ],
        description="List of separators for recursive splitting, ordered by semantic importance"
    )
    min_chunk_size: int = Field(default=50, description="Minimum size for a valid chunk")
    max_chunk_size: int = Field(default=2000, description="Maximum size for a chunk before forced splitting")
    preserve_sentence_boundaries: bool = Field(
        default=True, 
        description="Whether to prioritize keeping sentences intact"
    )
    preserve_paragraph_boundaries: bool = Field(
        default=True, 
        description="Whether to prioritize keeping paragraphs intact"
    )


class ChunkingService:
    """Service for intelligent text chunking with semantic boundary detection"""
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize the chunking service with configuration"""
        self.config = config or ChunkingConfig()
        self._setup_splitter()
        
    def _setup_splitter(self):
        """Setup the LangChain recursive text splitter with semantic boundary detection"""
        # Use enhanced separators based on configuration
        separators = self._get_semantic_separators()
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
            keep_separator=False,  # Don't keep separators in chunks
        )
        logger.info(f"Initialized text splitter with chunk_size={self.config.chunk_size}, overlap={self.config.chunk_overlap}")
        logger.debug(f"Using separators: {separators}")
    
    def _get_semantic_separators(self) -> List[str]:
        """
        Get separators ordered by semantic importance based on configuration
        
        Returns:
            List of separators ordered by semantic priority
        """
        separators = []
        
        # Paragraph boundaries (highest semantic priority)
        if self.config.preserve_paragraph_boundaries:
            separators.extend([
                "\n\n\n",  # Multiple line breaks
                "\n\n",    # Double line breaks (paragraph separators)
            ])
        
        # Sentence boundaries (high semantic priority)
        if self.config.preserve_sentence_boundaries:
            separators.extend([
                ". ",      # Period followed by space
                "! ",      # Exclamation followed by space  
                "? ",      # Question mark followed by space
                ".\n",     # Period followed by newline
                "!\n",     # Exclamation followed by newline
                "?\n",     # Question mark followed by newline
            ])
        
        # Clause and phrase boundaries (medium semantic priority)
        separators.extend([
            "; ",      # Semicolon
            ": ",      # Colon
            ", ",      # Comma (for lists and clauses)
            " - ",     # Dash with spaces
            " – ",     # En dash with spaces
            " — ",     # Em dash with spaces
        ])
        
        # Line boundaries
        separators.append("\n")
        
        # Word boundaries (lowest semantic priority)
        separators.extend([
            " ",       # Space between words
            "",        # Character-level split (last resort)
        ])
        
        # Use configured separators if provided, otherwise use semantic ones
        return self.config.separators if self.config.separators else separators
    
    def chunk_document_field(
        self,
        doctype: str,
        docname: str,
        field_name: str,
        content: str,
        source_url: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a single document field into semantic chunks
        
        Args:
            doctype: Type of the source document
            docname: Name/ID of the source document
            field_name: Name of the field being chunked
            content: Text content to chunk
            source_url: Optional URL to the source document
            
        Returns:
            List of DocumentChunk objects
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for {doctype}/{docname}/{field_name}")
            return []
            
        # Handle edge cases and clean content
        cleaned_content, warnings = self.handle_edge_cases(content)
        if not cleaned_content:
            logger.warning(f"Content became empty after cleaning for {doctype}/{docname}/{field_name}")
            return []
        
        content = cleaned_content
        
        # Check if content is too short to chunk meaningfully
        if len(content) < self.config.min_chunk_size:
            logger.info(f"Content too short to chunk for {doctype}/{docname}/{field_name}, creating single chunk")
            return self._create_single_chunk(doctype, docname, field_name, content, source_url, warnings)
        
        try:
            # Split text using LangChain recursive splitter
            text_chunks = self.splitter.split_text(content)
            
            if not text_chunks:
                logger.warning(f"No chunks created for {doctype}/{docname}/{field_name}")
                return []
            
            # Create DocumentChunk objects with metadata
            chunks = []
            total_chunks = len(text_chunks)
            
            for i, chunk_text in enumerate(text_chunks):
                # Skip empty chunks
                if not chunk_text.strip():
                    continue
                    
                chunk = self._create_document_chunk(
                    doctype=doctype,
                    docname=docname,
                    field_name=field_name,
                    content=chunk_text.strip(),
                    chunk_index=i,
                    total_chunks=total_chunks,
                    source_url=source_url,
                    warnings=warnings
                )
                chunks.append(chunk)
            
            logger.info(f"Created {len(chunks)} chunks for {doctype}/{docname}/{field_name}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking content for {doctype}/{docname}/{field_name}: {str(e)}")
            # Fallback to single chunk if splitting fails
            return self._create_single_chunk(doctype, docname, field_name, content, source_url)
    
    def chunk_document_fields(
        self,
        doctype: str,
        docname: str,
        field_data: Dict[str, str],
        source_url: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Chunk multiple fields from a document
        
        Args:
            doctype: Type of the source document
            docname: Name/ID of the source document
            field_data: Dictionary mapping field names to their content
            source_url: Optional URL to the source document
            
        Returns:
            List of DocumentChunk objects from all fields
        """
        all_chunks = []
        
        for field_name, content in field_data.items():
            if content:  # Only process non-empty fields
                field_chunks = self.chunk_document_field(
                    doctype=doctype,
                    docname=docname,
                    field_name=field_name,
                    content=content,
                    source_url=source_url
                )
                all_chunks.extend(field_chunks)
        
        logger.info(f"Created total of {len(all_chunks)} chunks for {doctype}/{docname}")
        return all_chunks
    
    def _create_single_chunk(
        self,
        doctype: str,
        docname: str,
        field_name: str,
        content: str,
        source_url: Optional[str] = None,
        warnings: Optional[List[str]] = None
    ) -> List[DocumentChunk]:
        """Create a single chunk for short content"""
        chunk = self._create_document_chunk(
            doctype=doctype,
            docname=docname,
            field_name=field_name,
            content=content,
            chunk_index=0,
            total_chunks=1,
            source_url=source_url,
            warnings=warnings
        )
        return [chunk]
    
    def _create_document_chunk(
        self,
        doctype: str,
        docname: str,
        field_name: str,
        content: str,
        chunk_index: int,
        total_chunks: int,
        source_url: Optional[str] = None,
        processing_time_ms: Optional[float] = None,
        warnings: Optional[List[str]] = None
    ) -> DocumentChunk:
        """Create a DocumentChunk object with enhanced metadata"""
        import time
        start_time = time.time()
        
        # Generate unique chunk ID with sanitization
        sanitized_doctype = self._sanitize_id_component(doctype)
        sanitized_docname = self._sanitize_id_component(docname)
        sanitized_field = self._sanitize_id_component(field_name)
        chunk_id = f"{sanitized_doctype}_{sanitized_docname}_{sanitized_field}_{chunk_index}"
        
        # Calculate enhanced metadata
        content_length = len(content)
        word_count = len(content.split()) if content.strip() else 0
        sentence_count = self._count_sentences(content)
        paragraph_count = self._count_paragraphs(content)
        semantic_boundaries = self.analyze_semantic_boundaries(content)
        quality_score = self._calculate_quality_score(content)
        
        # Create enhanced metadata
        metadata = DocumentMetadata(
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            timestamp=datetime.utcnow(),
            source_url=source_url,
            content_length=content_length,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            chunking_strategy="recursive",
            semantic_boundaries=semantic_boundaries,
            quality_score=quality_score,
            processing_time_ms=processing_time_ms or (time.time() - start_time) * 1000,
            error_count=0,
            warnings=warnings or []
        )
        
        # Create and return chunk
        return DocumentChunk(
            id=chunk_id,
            doctype=doctype,
            docname=docname,
            field_name=field_name,
            content=content,
            metadata=metadata
        )
    
    def validate_chunk(self, chunk: DocumentChunk) -> bool:
        """
        Validate a chunk meets quality requirements
        
        Args:
            chunk: DocumentChunk to validate
            
        Returns:
            True if chunk is valid, False otherwise
        """
        # Check content length
        if len(chunk.content) < self.config.min_chunk_size:
            logger.warning(f"Chunk {chunk.id} too short: {len(chunk.content)} characters")
            return False
            
        if len(chunk.content) > self.config.max_chunk_size:
            logger.warning(f"Chunk {chunk.id} too long: {len(chunk.content)} characters")
            return False
        
        # Check content is not just whitespace
        if not chunk.content.strip():
            logger.warning(f"Chunk {chunk.id} contains only whitespace")
            return False
        
        # Check required fields are present
        if not all([chunk.doctype, chunk.docname, chunk.field_name]):
            logger.warning(f"Chunk {chunk.id} missing required fields")
            return False
        
        return True
    
    def analyze_semantic_boundaries(self, text: str) -> Dict[str, int]:
        """
        Analyze semantic boundaries in text to help with chunking decisions
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with counts of different boundary types
        """
        if not text:
            return {}
        
        return {
            "paragraphs": text.count("\n\n"),
            "sentences": text.count(". ") + text.count("! ") + text.count("? "),
            "lines": text.count("\n"),
            "clauses": text.count("; ") + text.count(": "),
            "phrases": text.count(", "),
            "words": len(text.split()),
            "characters": len(text)
        }
    
    def optimize_chunk_boundaries(self, chunks: List[str]) -> List[str]:
        """
        Post-process chunks to optimize semantic boundaries
        
        Args:
            chunks: List of text chunks
            
        Returns:
            List of optimized chunks
        """
        if not chunks:
            return chunks
        
        optimized_chunks = []
        
        for chunk in chunks:
            # Clean up chunk boundaries
            cleaned_chunk = chunk.strip()
            
            # Remove orphaned punctuation at the beginning
            while cleaned_chunk and cleaned_chunk[0] in ".,;:!?":
                cleaned_chunk = cleaned_chunk[1:].strip()
            
            # Ensure sentences end properly
            if cleaned_chunk and not cleaned_chunk[-1] in ".!?":
                # If chunk doesn't end with sentence punctuation, try to find a good break point
                words = cleaned_chunk.split()
                if len(words) > 1:
                    # Look for the last complete sentence
                    for i in range(len(words) - 1, 0, -1):
                        if words[i-1].endswith(('.', '!', '?')):
                            cleaned_chunk = ' '.join(words[:i])
                            break
            
            if cleaned_chunk:
                optimized_chunks.append(cleaned_chunk)
        
        return optimized_chunks
    
    def get_chunk_overlap_analysis(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """
        Analyze overlap between consecutive chunks
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Dictionary with overlap analysis
        """
        if len(chunks) < 2:
            return {"overlap_analysis": "Not applicable - less than 2 chunks"}
        
        overlaps = []
        
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i].content
            next_chunk = chunks[i + 1].content
            
            # Find common suffix/prefix
            overlap_length = 0
            min_length = min(len(current_chunk), len(next_chunk))
            
            # Check for overlap at the end of current and beginning of next
            for j in range(1, min_length + 1):
                if current_chunk[-j:] == next_chunk[:j]:
                    overlap_length = j
            
            overlaps.append(overlap_length)
        
        if overlaps:
            return {
                "avg_overlap": sum(overlaps) / len(overlaps),
                "min_overlap": min(overlaps),
                "max_overlap": max(overlaps),
                "total_overlaps": len(overlaps)
            }
        
        return {"overlap_analysis": "No overlaps detected"}
    
    def get_chunk_statistics(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """
        Get comprehensive statistics about a list of chunks
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Dictionary with chunk statistics
        """
        if not chunks:
            return {"total_chunks": 0}
        
        chunk_sizes = [len(chunk.content) for chunk in chunks]
        
        # Basic statistics
        stats = {
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(chunk_sizes) / len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "total_content_length": sum(chunk_sizes),
            "unique_documents": len(set(f"{chunk.doctype}_{chunk.docname}" for chunk in chunks)),
            "unique_fields": len(set(chunk.field_name for chunk in chunks))
        }
        
        # Add semantic boundary analysis for all chunks combined
        all_content = " ".join(chunk.content for chunk in chunks)
        stats["semantic_boundaries"] = self.analyze_semantic_boundaries(all_content)
        
        # Add overlap analysis
        stats["overlap_analysis"] = self.get_chunk_overlap_analysis(chunks)
        
        return stats
    
    def _sanitize_id_component(self, component: str) -> str:
        """
        Sanitize a component for use in chunk IDs
        
        Args:
            component: String component to sanitize
            
        Returns:
            Sanitized string safe for use in IDs
        """
        if not component:
            return "unknown"
        
        # Replace problematic characters with underscores
        import re
        sanitized = re.sub(r'[^\w\-]', '_', str(component))
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Ensure it's not empty after sanitization
        return sanitized if sanitized else "unknown"
    
    def _count_sentences(self, text: str) -> int:
        """
        Count sentences in text using multiple sentence ending patterns
        
        Args:
            text: Text to analyze
            
        Returns:
            Number of sentences detected
        """
        if not text:
            return 0
        
        import re
        # Pattern to match sentence endings (period, exclamation, question mark)
        # followed by whitespace or end of string
        sentence_pattern = r'[.!?]+(?:\s|$)'
        matches = re.findall(sentence_pattern, text)
        return len(matches)
    
    def _count_paragraphs(self, text: str) -> int:
        """
        Count paragraphs in text based on double newlines
        
        Args:
            text: Text to analyze
            
        Returns:
            Number of paragraphs detected
        """
        if not text:
            return 0
        
        # Split by double newlines and count non-empty parts
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return len(paragraphs)
    
    def _calculate_quality_score(self, content: str) -> float:
        """
        Calculate a quality score for a chunk based on various factors
        
        Args:
            content: Chunk content to evaluate
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not content or not content.strip():
            return 0.0
        
        score = 0.0
        factors = 0
        
        # Factor 1: Length appropriateness (0.3 weight)
        length = len(content)
        if self.config.min_chunk_size <= length <= self.config.max_chunk_size:
            # Optimal length range
            if length >= self.config.chunk_size * 0.7:  # Close to target size
                score += 0.3
            else:
                score += 0.2  # Acceptable but not optimal
        elif length < self.config.min_chunk_size:
            score += 0.1  # Too short
        else:
            score += 0.15  # Too long but still usable
        factors += 1
        
        # Factor 2: Sentence completeness (0.25 weight)
        sentence_endings = content.count('.') + content.count('!') + content.count('?')
        if sentence_endings > 0:
            # Check if chunk ends with sentence punctuation
            if content.strip().endswith(('.', '!', '?')):
                score += 0.25
            else:
                score += 0.15  # Has sentences but doesn't end cleanly
        else:
            score += 0.05  # No clear sentence structure
        factors += 1
        
        # Factor 3: Word density and readability (0.2 weight)
        words = content.split()
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            if 3 <= avg_word_length <= 7:  # Reasonable word length
                score += 0.2
            else:
                score += 0.1
        factors += 1
        
        # Factor 4: Paragraph structure (0.15 weight)
        paragraphs = content.count('\n\n')
        if paragraphs == 0 and length < self.config.chunk_size:
            score += 0.15  # Single paragraph, appropriate for size
        elif paragraphs > 0:
            score += 0.1  # Multiple paragraphs
        else:
            score += 0.05  # No clear paragraph structure
        factors += 1
        
        # Factor 5: Special characters and formatting (0.1 weight)
        special_chars = sum(1 for c in content if c in '.,;:!?()-[]{}')
        if special_chars > 0:
            score += 0.1  # Has punctuation and structure
        else:
            score += 0.05  # Limited punctuation
        factors += 1
        
        # Normalize score to 0-1 range
        return min(1.0, score)
    
    def handle_edge_cases(self, content: str) -> tuple[str, List[str]]:
        """
        Handle edge cases in content and return cleaned content with warnings
        
        Args:
            content: Raw content to process
            
        Returns:
            Tuple of (cleaned_content, warnings_list)
        """
        warnings = []
        
        if not content:
            return "", ["Empty content provided"]
        
        original_length = len(content)
        cleaned_content = content
        
        # Handle null bytes and control characters
        if '\x00' in cleaned_content:
            cleaned_content = cleaned_content.replace('\x00', '')
            warnings.append("Removed null bytes from content")
        
        # Handle other problematic control characters
        import re
        control_chars = re.findall(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', cleaned_content)
        if control_chars:
            cleaned_content = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned_content)
            warnings.append(f"Removed {len(control_chars)} control characters")
        
        # Handle excessive whitespace
        if re.search(r'\s{10,}', cleaned_content):
            cleaned_content = re.sub(r'\s{3,}', ' ', cleaned_content)
            warnings.append("Normalized excessive whitespace")
        
        # Handle very long lines (potential formatting issues)
        lines = cleaned_content.split('\n')
        long_lines = [i for i, line in enumerate(lines) if len(line) > 1000]
        if long_lines:
            warnings.append(f"Found {len(long_lines)} very long lines (>1000 chars)")
        
        # Handle mixed line endings
        if '\r\n' in cleaned_content or '\r' in cleaned_content:
            cleaned_content = cleaned_content.replace('\r\n', '\n').replace('\r', '\n')
            warnings.append("Normalized line endings")
        
        # Handle Unicode issues
        try:
            cleaned_content.encode('utf-8')
        except UnicodeEncodeError:
            # Try to clean up problematic Unicode
            cleaned_content = cleaned_content.encode('utf-8', errors='ignore').decode('utf-8')
            warnings.append("Fixed Unicode encoding issues")
        
        # Check for significant content loss
        final_length = len(cleaned_content)
        if final_length < original_length * 0.9:  # Lost more than 10% of content
            warnings.append(f"Significant content loss during cleaning: {original_length} -> {final_length} chars")
        
        # Handle empty result after cleaning
        if not cleaned_content.strip():
            warnings.append("Content became empty after cleaning")
            return "", warnings
        
        return cleaned_content.strip(), warnings
    
    def validate_and_repair_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Validate chunks and attempt to repair common issues
        
        Args:
            chunks: List of chunks to validate and repair
            
        Returns:
            List of validated and repaired chunks
        """
        if not chunks:
            return chunks
        
        repaired_chunks = []
        
        for chunk in chunks:
            # Create a copy to avoid modifying the original
            repaired_chunk = DocumentChunk(
                id=chunk.id,
                doctype=chunk.doctype,
                docname=chunk.docname,
                field_name=chunk.field_name,
                content=chunk.content,
                metadata=chunk.metadata,
                embedding=chunk.embedding
            )
            
            # Handle edge cases in content
            cleaned_content, warnings = self.handle_edge_cases(chunk.content)
            
            if cleaned_content:
                repaired_chunk.content = cleaned_content
                
                # Update metadata with warnings
                if warnings:
                    repaired_chunk.metadata.warnings.extend(warnings)
                    repaired_chunk.metadata.error_count = len(warnings)
                
                # Recalculate metadata if content changed significantly
                if cleaned_content != chunk.content:
                    repaired_chunk.metadata.content_length = len(cleaned_content)
                    repaired_chunk.metadata.word_count = len(cleaned_content.split()) if cleaned_content.strip() else 0
                    repaired_chunk.metadata.sentence_count = self._count_sentences(cleaned_content)
                    repaired_chunk.metadata.paragraph_count = self._count_paragraphs(cleaned_content)
                    repaired_chunk.metadata.semantic_boundaries = self.analyze_semantic_boundaries(cleaned_content)
                    repaired_chunk.metadata.quality_score = self._calculate_quality_score(cleaned_content)
                
                # Only include chunk if it passes validation
                if self.validate_chunk(repaired_chunk):
                    repaired_chunks.append(repaired_chunk)
                else:
                    logger.warning(f"Chunk {chunk.id} failed validation after repair")
            else:
                logger.warning(f"Chunk {chunk.id} became empty after cleaning, skipping")
        
        return repaired_chunks