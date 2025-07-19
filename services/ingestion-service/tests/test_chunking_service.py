"""
Unit tests for the chunking service
"""

import pytest
from datetime import datetime
import sys
import os

# Add the parent directory to the path to import the service
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.chunking_service import ChunkingService, ChunkingConfig
from shared.models.document import DocumentChunk, DocumentMetadata


class TestChunkingService:
    """Test cases for ChunkingService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.service = ChunkingService()
        self.test_doctype = "Test Document"
        self.test_docname = "TEST-001"
        self.test_field = "description"
        self.test_url = "https://example.com/doc/TEST-001"
    
    def test_initialization_default_config(self):
        """Test service initialization with default configuration"""
        service = ChunkingService()
        assert service.config.chunk_size == 1000
        assert service.config.chunk_overlap == 200
        assert service.config.min_chunk_size == 50
        assert service.splitter is not None
    
    def test_initialization_custom_config(self):
        """Test service initialization with custom configuration"""
        config = ChunkingConfig(
            chunk_size=500,
            chunk_overlap=100,
            min_chunk_size=25
        )
        service = ChunkingService(config)
        assert service.config.chunk_size == 500
        assert service.config.chunk_overlap == 100
        assert service.config.min_chunk_size == 25
    
    def test_chunk_short_content(self):
        """Test chunking content shorter than minimum chunk size"""
        short_content = "This is a short text."
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, short_content
        )
        
        assert len(chunks) == 1
        assert chunks[0].content == short_content
        assert chunks[0].metadata.chunk_index == 0
        assert chunks[0].metadata.total_chunks == 1
        assert chunks[0].doctype == self.test_doctype
        assert chunks[0].docname == self.test_docname
        assert chunks[0].field_name == self.test_field
    
    def test_chunk_empty_content(self):
        """Test chunking empty or whitespace-only content"""
        # Empty string
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, ""
        )
        assert len(chunks) == 0
        
        # Whitespace only
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, "   \n\t  "
        )
        assert len(chunks) == 0
        
        # None content
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, None
        )
        assert len(chunks) == 0
    
    def test_chunk_long_content(self):
        """Test chunking content that requires multiple chunks"""
        # Create content longer than default chunk size
        long_content = "This is a test paragraph. " * 100  # ~2600 characters
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, long_content
        )
        
        assert len(chunks) > 1
        
        # Check that all chunks have content
        for chunk in chunks:
            assert len(chunk.content) > 0
            assert chunk.doctype == self.test_doctype
            assert chunk.docname == self.test_docname
            assert chunk.field_name == self.test_field
        
        # Check chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.metadata.chunk_index == i
            assert chunk.metadata.total_chunks == len(chunks)
    
    def test_chunk_with_semantic_boundaries(self):
        """Test that chunking respects semantic boundaries"""
        content = """This is the first paragraph. It contains several sentences. This should help test semantic boundary detection.

This is the second paragraph. It also contains multiple sentences. The chunker should try to keep paragraphs together when possible.

This is the third paragraph. It's designed to test how the recursive splitter handles different types of content and boundaries."""
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Should create at least one chunk
        assert len(chunks) >= 1
        
        # Check that chunks don't break in the middle of words
        for chunk in chunks:
            # Content should not start or end with partial words (basic check)
            assert not chunk.content.startswith(" ")
            assert chunk.content.strip() == chunk.content
    
    def test_chunk_multiple_fields(self):
        """Test chunking multiple fields from a document"""
        field_data = {
            "title": "Test Document Title",
            "description": "This is a longer description that might be chunked. " * 20,
            "notes": "Some additional notes about the document.",
            "empty_field": "",
            "whitespace_field": "   \n\t  "
        }
        
        chunks = self.service.chunk_document_fields(
            self.test_doctype, self.test_docname, field_data, self.test_url
        )
        
        # Should have chunks from non-empty fields
        assert len(chunks) >= 3  # title, description (possibly multiple), notes
        
        # Check that chunks from different fields are properly identified
        field_names = set(chunk.field_name for chunk in chunks)
        assert "title" in field_names
        assert "description" in field_names
        assert "notes" in field_names
        assert "empty_field" not in field_names
        assert "whitespace_field" not in field_names
        
        # Check source URL is preserved
        for chunk in chunks:
            assert chunk.metadata.source_url == self.test_url
    
    def test_chunk_validation(self):
        """Test chunk validation functionality"""
        # Valid chunk
        valid_chunk = DocumentChunk(
            id="test_chunk",
            doctype=self.test_doctype,
            docname=self.test_docname,
            field_name=self.test_field,
            content="This is a valid chunk with sufficient content length.",
            metadata=DocumentMetadata(
                chunk_index=0, total_chunks=1,
                content_length=55, word_count=10
            )
        )
        assert self.service.validate_chunk(valid_chunk) is True
        
        # Too short chunk
        short_chunk = DocumentChunk(
            id="short_chunk",
            doctype=self.test_doctype,
            docname=self.test_docname,
            field_name=self.test_field,
            content="Short",
            metadata=DocumentMetadata(
                chunk_index=0, total_chunks=1,
                content_length=5, word_count=1
            )
        )
        assert self.service.validate_chunk(short_chunk) is False
        
        # Whitespace only chunk
        whitespace_chunk = DocumentChunk(
            id="whitespace_chunk",
            doctype=self.test_doctype,
            docname=self.test_docname,
            field_name=self.test_field,
            content="   \n\t  ",
            metadata=DocumentMetadata(
                chunk_index=0, total_chunks=1,
                content_length=8, word_count=0
            )
        )
        assert self.service.validate_chunk(whitespace_chunk) is False
        
        # Missing required fields
        incomplete_chunk = DocumentChunk(
            id="incomplete_chunk",
            doctype="",
            docname=self.test_docname,
            field_name=self.test_field,
            content="This chunk is missing doctype.",
            metadata=DocumentMetadata(
                chunk_index=0, total_chunks=1,
                content_length=32, word_count=5
            )
        )
        assert self.service.validate_chunk(incomplete_chunk) is False
    
    def test_chunk_statistics(self):
        """Test chunk statistics calculation"""
        # Create test chunks
        chunks = [
            DocumentChunk(
                id="chunk1",
                doctype="Doc1",
                docname="DOC-001",
                field_name="field1",
                content="A" * 100,
                metadata=DocumentMetadata(
                    chunk_index=0, total_chunks=2,
                    content_length=100, word_count=1
                )
            ),
            DocumentChunk(
                id="chunk2",
                doctype="Doc1",
                docname="DOC-001",
                field_name="field2",
                content="B" * 200,
                metadata=DocumentMetadata(
                    chunk_index=1, total_chunks=2,
                    content_length=200, word_count=1
                )
            ),
            DocumentChunk(
                id="chunk3",
                doctype="Doc2",
                docname="DOC-002",
                field_name="field1",
                content="C" * 150,
                metadata=DocumentMetadata(
                    chunk_index=0, total_chunks=1,
                    content_length=150, word_count=1
                )
            )
        ]
        
        stats = self.service.get_chunk_statistics(chunks)
        
        assert stats["total_chunks"] == 3
        assert stats["avg_chunk_size"] == 150.0  # (100 + 200 + 150) / 3
        assert stats["min_chunk_size"] == 100
        assert stats["max_chunk_size"] == 200
        assert stats["total_content_length"] == 450
        assert stats["unique_documents"] == 2
        assert stats["unique_fields"] == 2
        
        # Test empty chunks list
        empty_stats = self.service.get_chunk_statistics([])
        assert empty_stats["total_chunks"] == 0
    
    def test_chunk_id_generation(self):
        """Test that chunk IDs are generated correctly and uniquely"""
        content = "This is test content for ID generation. " * 30
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Check that all chunk IDs are unique
        chunk_ids = [chunk.id for chunk in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))
        
        # Check ID format (accounting for sanitization)
        for i, chunk in enumerate(chunks):
            # The doctype "Test Document" gets sanitized to "Test_Document"
            expected_id = f"Test_Document_{self.test_docname}_{self.test_field}_{i}"
            assert chunk.id == expected_id
    
    def test_chunk_metadata_preservation(self):
        """Test that metadata is properly preserved in chunks"""
        content = "Test content for metadata preservation."
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content, self.test_url
        )
        
        assert len(chunks) == 1
        chunk = chunks[0]
        
        # Check basic metadata fields
        assert chunk.metadata.chunk_index == 0
        assert chunk.metadata.total_chunks == 1
        assert chunk.metadata.source_url == self.test_url
        assert isinstance(chunk.metadata.timestamp, datetime)
        
        # Check enhanced metadata fields
        assert chunk.metadata.content_length == len(content)
        assert chunk.metadata.word_count > 0
        assert chunk.metadata.sentence_count >= 0
        assert chunk.metadata.paragraph_count >= 0
        assert chunk.metadata.chunking_strategy == "recursive"
        assert isinstance(chunk.metadata.semantic_boundaries, dict)
        assert chunk.metadata.quality_score is not None
        assert 0.0 <= chunk.metadata.quality_score <= 1.0
        assert chunk.metadata.processing_time_ms is not None
        assert chunk.metadata.processing_time_ms >= 0
        assert isinstance(chunk.metadata.warnings, list)
        assert chunk.metadata.error_count >= 0
        
        # Check that timestamp is recent (within last minute)
        time_diff = datetime.utcnow() - chunk.metadata.timestamp
        assert time_diff.total_seconds() < 60
    
    def test_custom_separators(self):
        """Test chunking with custom separators"""
        config = ChunkingConfig(
            chunk_size=30,  # Force splitting with smaller chunk size
            chunk_overlap=5,
            separators=["|", ";", " "]
        )
        service = ChunkingService(config)
        
        content = "First section|Second section|Third section|Fourth section|Fifth section"
        
        chunks = service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Should split on the custom separator due to size constraints
        assert len(chunks) >= 1
        
        # If multiple chunks are created, check that splits respect the custom separator
        if len(chunks) > 1:
            for chunk in chunks:
                # Should not contain the separator at the beginning or end
                assert not chunk.content.startswith("|")
                assert not chunk.content.endswith("|")
        
        # Verify that the service uses custom separators
        assert service.config.separators == ["|", ";", " "]
    
    def test_semantic_boundary_preservation(self):
        """Test that semantic boundaries (sentences, paragraphs) are preserved"""
        content = """This is the first paragraph with multiple sentences. It should be kept together when possible. This tests sentence boundary detection.

This is the second paragraph. It also contains multiple sentences. The chunker should prioritize paragraph boundaries.

This is the third paragraph with a list: item one, item two, item three. The comma separators should be lower priority than sentence boundaries."""
        
        # Use smaller chunk size to force splitting
        config = ChunkingConfig(
            chunk_size=200,
            chunk_overlap=50,
            preserve_sentence_boundaries=True,
            preserve_paragraph_boundaries=True
        )
        service = ChunkingService(config)
        
        chunks = service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Should create multiple chunks due to size limit
        assert len(chunks) > 1
        
        # Check that chunks don't break sentences inappropriately
        for chunk in chunks:
            # Chunks should not start with lowercase (indicating broken sentence)
            if chunk.content and chunk.content[0].isalpha():
                assert chunk.content[0].isupper(), f"Chunk starts with lowercase: '{chunk.content[:50]}...'"
            
            # Chunks should generally end with sentence punctuation or be incomplete due to size limits
            content_stripped = chunk.content.strip()
            if content_stripped and len(content_stripped) < config.chunk_size - 50:  # Allow some tolerance
                # If chunk is well under size limit, it should end properly
                assert content_stripped[-1] in '.!?\n' or content_stripped.endswith('...'), \
                    f"Chunk doesn't end properly: '...{content_stripped[-50:]}'"
    
    def test_paragraph_boundary_detection(self):
        """Test specific paragraph boundary detection"""
        content = "Paragraph one.\n\nParagraph two with more content.\n\n\nParagraph three after multiple breaks."
        
        config = ChunkingConfig(
            chunk_size=50,  # Force splitting
            chunk_overlap=20,  # Smaller than chunk_size
            preserve_paragraph_boundaries=True
        )
        service = ChunkingService(config)
        
        chunks = service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Should respect paragraph boundaries
        assert len(chunks) >= 2
        
        # Check that paragraph breaks are preserved
        for chunk in chunks:
            # Chunks should not contain paragraph breaks in the middle inappropriately
            content_lines = chunk.content.split('\n')
            # If there are multiple lines, they should be related content
            assert len(content_lines) <= 3  # Allow some flexibility
    
    def test_sentence_boundary_detection(self):
        """Test specific sentence boundary detection"""
        content = "First sentence. Second sentence! Third sentence? Fourth sentence with more content."
        
        config = ChunkingConfig(
            chunk_size=30,  # Force splitting at sentence boundaries
            chunk_overlap=10,  # Smaller than chunk_size
            preserve_sentence_boundaries=True
        )
        service = ChunkingService(config)
        
        chunks = service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should contain complete sentences when possible
        for chunk in chunks:
            # Should not break in the middle of sentences
            if '. ' in chunk.content:
                # If chunk contains sentence breaks, it should end after a complete sentence
                sentences = chunk.content.split('. ')
                if len(sentences) > 1:
                    # Last part should be a complete sentence or fragment
                    assert sentences[-1].strip() != ''
    
    def test_configurable_overlap_handling(self):
        """Test configurable chunk overlap functionality"""
        content = "This is a test document with multiple sentences. " * 20  # ~1000 characters
        
        # Test different overlap configurations
        overlap_configs = [0, 50, 100, 200]
        
        for overlap in overlap_configs:
            config = ChunkingConfig(
                chunk_size=300,
                chunk_overlap=overlap
            )
            service = ChunkingService(config)
            
            chunks = service.chunk_document_field(
                self.test_doctype, self.test_docname, self.test_field, content
            )
            
            if len(chunks) > 1:
                # Verify overlap is approximately correct
                overlap_analysis = service.get_chunk_overlap_analysis(chunks)
                if 'avg_overlap' in overlap_analysis:
                    # Allow some tolerance in overlap detection
                    assert overlap_analysis['avg_overlap'] >= 0
                    # For non-zero overlap configs, should have some overlap
                    if overlap > 0:
                        assert overlap_analysis['avg_overlap'] > 0
    
    def test_semantic_boundary_analysis(self):
        """Test semantic boundary analysis functionality"""
        content = """This is paragraph one. It has multiple sentences! Does it work?

This is paragraph two. It contains: colons, semicolons; and commas, for testing."""
        
        analysis = self.service.analyze_semantic_boundaries(content)
        
        # Check expected boundary counts
        assert analysis['paragraphs'] == 1  # One double newline
        assert analysis['sentences'] >= 3   # At least 3 sentence endings (. ! ?)
        assert analysis['lines'] >= 2       # At least 2 newlines
        assert analysis['clauses'] >= 1     # At least 1 colon or semicolon
        assert analysis['phrases'] >= 1     # At least 1 comma
        assert analysis['words'] > 10       # Multiple words
        assert analysis['characters'] > 50  # Multiple characters
        
        # Test empty content
        empty_analysis = self.service.analyze_semantic_boundaries("")
        assert empty_analysis == {}
    
    def test_chunk_boundary_optimization(self):
        """Test chunk boundary optimization functionality"""
        # Test chunks with problematic boundaries
        problematic_chunks = [
            ",This starts with comma",
            "This ends with orphaned punctuation;",
            "This is a complete sentence.",
            "This is incomplete without punctuation",
            "  This has extra whitespace  "
        ]
        
        optimized = self.service.optimize_chunk_boundaries(problematic_chunks)
        
        # Check that boundaries are cleaned up
        assert len(optimized) <= len(problematic_chunks)  # Some might be filtered out
        
        for chunk in optimized:
            # Should not start with punctuation
            assert not chunk.startswith((',', ';', ':', '.', '!', '?'))
            # Should be properly trimmed
            assert chunk == chunk.strip()
            # Should not be empty
            assert len(chunk) > 0
    
    def test_enhanced_chunk_statistics(self):
        """Test enhanced chunk statistics with semantic analysis"""
        content = """First paragraph with sentences. Multiple sentences here!

Second paragraph with different content. More sentences and clauses: like this one; and this one."""
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        stats = self.service.get_chunk_statistics(chunks)
        
        # Check that enhanced statistics are included
        assert 'semantic_boundaries' in stats
        assert 'overlap_analysis' in stats
        
        # Check semantic boundaries analysis
        boundaries = stats['semantic_boundaries']
        assert 'paragraphs' in boundaries
        assert 'sentences' in boundaries
        assert 'words' in boundaries
        assert 'characters' in boundaries
        
        # Check basic statistics are still present
        assert 'total_chunks' in stats
        assert 'avg_chunk_size' in stats
        assert stats['total_chunks'] == len(chunks)
    
    def test_preserve_boundary_configuration(self):
        """Test configuration options for preserving different boundary types"""
        content = "Sentence one. Sentence two!\n\nNew paragraph here. Another sentence."
        
        # Test with sentence boundaries disabled
        config_no_sentences = ChunkingConfig(
            chunk_size=100,
            chunk_overlap=20,
            preserve_sentence_boundaries=False,
            preserve_paragraph_boundaries=True
        )
        service_no_sentences = ChunkingService(config_no_sentences)
        
        # Test with paragraph boundaries disabled
        config_no_paragraphs = ChunkingConfig(
            chunk_size=100,
            chunk_overlap=20,
            preserve_sentence_boundaries=True,
            preserve_paragraph_boundaries=False
        )
        service_no_paragraphs = ChunkingService(config_no_paragraphs)
        
        # Test with both enabled (default)
        config_both = ChunkingConfig(
            chunk_size=100,
            chunk_overlap=20,
            preserve_sentence_boundaries=True,
            preserve_paragraph_boundaries=True
        )
        service_both = ChunkingService(config_both)
        
        chunks_no_sentences = service_no_sentences.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        chunks_no_paragraphs = service_no_paragraphs.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        chunks_both = service_both.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        # All should create chunks
        assert len(chunks_no_sentences) > 0
        assert len(chunks_no_paragraphs) > 0
        assert len(chunks_both) > 0
        
        # The different configurations should potentially create different chunking patterns
        # (This is a behavioral test - exact results may vary based on content and size limits)
    
    def test_error_handling(self):
        """Test error handling in chunking process"""
        # Test with problematic content that might cause issues
        problematic_content = "\x00\x01\x02" + "Normal text content"
        
        # Should not raise exception, should handle gracefully
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, problematic_content
        )
        
        # Should still create chunks (fallback behavior)
        assert len(chunks) >= 1
        
        # Content should be cleaned
        for chunk in chunks:
            assert chunk.content is not None
            assert len(chunk.content) > 0
    
    def test_edge_case_handling(self):
        """Test comprehensive edge case handling"""
        # Test null bytes
        content_with_nulls = "This content has\x00null bytes\x00in it."
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content_with_nulls
        )
        assert len(chunks) == 1
        assert '\x00' not in chunks[0].content
        assert len(chunks[0].metadata.warnings) > 0
        assert any("null bytes" in warning for warning in chunks[0].metadata.warnings)
        
        # Test control characters
        content_with_control = "This has\x01\x02control\x03chars."
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content_with_control
        )
        assert len(chunks) == 1
        assert not any(ord(c) < 32 and c not in '\n\t' for c in chunks[0].content)
        assert any("control characters" in warning for warning in chunks[0].metadata.warnings)
        
        # Test excessive whitespace
        content_with_whitespace = "This has          excessive     whitespace."
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content_with_whitespace
        )
        assert len(chunks) == 1
        assert "          " not in chunks[0].content
        
        # Test mixed line endings
        content_mixed_lines = "Line one\r\nLine two\rLine three\nLine four"
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content_mixed_lines
        )
        assert len(chunks) == 1
        assert '\r' not in chunks[0].content
        assert any("line endings" in warning for warning in chunks[0].metadata.warnings)
    
    def test_enhanced_metadata_calculation(self):
        """Test enhanced metadata calculation"""
        content = """This is a test document with multiple sentences. It has paragraphs too!
        
        This is the second paragraph. It contains: colons, semicolons; and various punctuation marks."""
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        assert len(chunks) == 1
        chunk = chunks[0]
        metadata = chunk.metadata
        
        # Test content length (should match the cleaned content length)
        assert metadata.content_length == len(chunk.content)
        
        # Test word count
        expected_words = len(content.strip().split())
        assert metadata.word_count == expected_words
        
        # Test sentence count (should detect multiple sentences)
        assert metadata.sentence_count >= 2
        
        # Test paragraph count (should detect paragraph break)
        assert metadata.paragraph_count >= 1
        
        # Test semantic boundaries
        boundaries = metadata.semantic_boundaries
        assert 'sentences' in boundaries
        assert 'paragraphs' in boundaries
        assert 'words' in boundaries
        assert 'characters' in boundaries
        assert boundaries['words'] > 10
        assert boundaries['characters'] > 50
        
        # Test quality score
        assert 0.0 <= metadata.quality_score <= 1.0
        
        # Test processing time
        assert metadata.processing_time_ms >= 0
    
    def test_chunk_id_sanitization(self):
        """Test chunk ID sanitization for problematic characters"""
        problematic_doctype = "Test/Document With Spaces & Special-Chars!"
        problematic_docname = "DOC-001@#$%"
        problematic_field = "field.name with/spaces"
        
        chunks = self.service.chunk_document_field(
            problematic_doctype, problematic_docname, problematic_field, "Test content"
        )
        
        assert len(chunks) == 1
        chunk_id = chunks[0].id
        
        # Should not contain problematic characters
        assert '/' not in chunk_id
        assert '@' not in chunk_id
        assert '#' not in chunk_id
        assert '$' not in chunk_id
        assert '%' not in chunk_id
        assert '!' not in chunk_id
        assert ' ' not in chunk_id
        assert '.' not in chunk_id
        
        # Should contain underscores as replacements
        assert '_' in chunk_id
        
        # Should end with chunk index
        assert chunk_id.endswith('_0')
    
    def test_quality_score_calculation(self):
        """Test quality score calculation for different content types"""
        # High quality content (complete sentences, good length)
        high_quality = "This is a well-formed document with complete sentences. It has proper punctuation and good structure. The content is meaningful and well-organized."
        chunks_hq = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, high_quality
        )
        hq_score = chunks_hq[0].metadata.quality_score
        
        # Low quality content (fragments, poor structure)
        low_quality = "fragment without punctuation another fragment no structure"
        chunks_lq = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, low_quality
        )
        lq_score = chunks_lq[0].metadata.quality_score
        
        # High quality should score better than low quality
        assert hq_score > lq_score
        assert hq_score > 0.5  # Should be reasonably high
        assert lq_score < 0.8  # Should be lower due to poor structure
    
    def test_validate_and_repair_chunks(self):
        """Test chunk validation and repair functionality"""
        # Create chunks with various issues
        problematic_chunks = [
            DocumentChunk(
                id="chunk1",
                doctype="Test",
                docname="DOC-001",
                field_name="field1",
                content="This is good content without any issues that should pass validation.",
                metadata=DocumentMetadata(
                    chunk_index=0, total_chunks=3,
                    content_length=67, word_count=12
                )
            ),
            DocumentChunk(
                id="chunk2",
                doctype="Test",
                docname="DOC-001",
                field_name="field2",
                content="\x00This content has\x01null bytes\x02and control characters that need cleaning.",
                metadata=DocumentMetadata(
                    chunk_index=1, total_chunks=3,
                    content_length=78, word_count=12
                )
            ),
            DocumentChunk(
                id="chunk3",
                doctype="Test",
                docname="DOC-001",
                field_name="field3",
                content="   \n\t  ",  # Whitespace only
                metadata=DocumentMetadata(
                    chunk_index=2, total_chunks=3,
                    content_length=8, word_count=0
                )
            )
        ]
        
        repaired_chunks = self.service.validate_and_repair_chunks(problematic_chunks)
        
        # Should have fewer chunks (whitespace-only chunk should be removed)
        assert len(repaired_chunks) < len(problematic_chunks)
        assert len(repaired_chunks) == 2
        
        # Check that problematic content was cleaned
        for chunk in repaired_chunks:
            assert '\x00' not in chunk.content
            assert '\x01' not in chunk.content
            assert '\x02' not in chunk.content
            assert chunk.content.strip() == chunk.content
            assert len(chunk.content) > 0
        
        # Check that warnings were added for repaired chunks
        repaired_chunk_with_issues = next(
            (c for c in repaired_chunks if c.id == "chunk2"), None
        )
        assert repaired_chunk_with_issues is not None
        assert len(repaired_chunk_with_issues.metadata.warnings) > 0
        assert repaired_chunk_with_issues.metadata.error_count > 0
    
    def test_sentence_and_paragraph_counting(self):
        """Test sentence and paragraph counting accuracy"""
        content = """First sentence. Second sentence! Third sentence?
        
        This is a new paragraph. It has multiple sentences. Does the counting work correctly?
        
        Final paragraph here."""
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        assert len(chunks) == 1
        metadata = chunks[0].metadata
        
        # Should count sentences correctly (at least 6 sentences)
        assert metadata.sentence_count >= 6
        
        # Should count paragraphs correctly (after whitespace normalization, may be fewer)
        assert metadata.paragraph_count >= 1
    
    def test_processing_time_tracking(self):
        """Test that processing time is tracked"""
        content = "Test content for processing time tracking."
        
        chunks = self.service.chunk_document_field(
            self.test_doctype, self.test_docname, self.test_field, content
        )
        
        assert len(chunks) == 1
        assert chunks[0].metadata.processing_time_ms is not None
        assert chunks[0].metadata.processing_time_ms >= 0
        # Should be reasonable processing time (less than 1 second for simple content)
        assert chunks[0].metadata.processing_time_ms < 1000


class TestChunkingConfig:
    """Test cases for ChunkingConfig"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = ChunkingConfig()
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.min_chunk_size == 50
        assert config.max_chunk_size == 2000
        assert len(config.separators) > 0
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = ChunkingConfig(
            chunk_size=500,
            chunk_overlap=100,
            min_chunk_size=25,
            max_chunk_size=1500,
            separators=["\n", ". ", " "]
        )
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100
        assert config.min_chunk_size == 25
        assert config.max_chunk_size == 1500
        assert config.separators == ["\n", ". ", " "]


if __name__ == "__main__":
    pytest.main([__file__])