"""
Unit tests for query service semantic search functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List, Dict, Any

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.query_service import QueryService
from models.responses import SearchResponse, SearchResultChunk


class TestQueryService:
    """Test cases for QueryService"""
    
    @pytest.fixture
    async def mock_query_service(self):
        """Create a query service with mocked dependencies"""
        service = QueryService()
        
        # Mock embedding service
        service.embedding_service = Mock()
        service.embedding_service.is_ready.return_value = True
        service.embedding_service.generate_embedding = AsyncMock()
        service.embedding_service.get_cache_size.return_value = 10
        service.embedding_service.clear_cache = AsyncMock(return_value=10)
        service.embedding_service.cleanup = AsyncMock()
        
        # Mock Qdrant service
        service.qdrant_service = Mock()
        service.qdrant_service.is_ready.return_value = True
        service.qdrant_service.search_vectors = AsyncMock()
        service.qdrant_service.get_collection_info = AsyncMock()
        service.qdrant_service.cleanup = AsyncMock()
        
        service._ready = True
        return service
    
    @pytest.fixture
    def sample_search_results(self):
        """Sample search results from Qdrant"""
        # Create a simple mock SearchResult class for testing
        class SearchResult:
            def __init__(self, id, score, payload):
                self.id = id
                self.score = score
                self.payload = payload
        
        return [
            SearchResult(
                id="doc1_field1_chunk1",
                score=0.95,
                payload={
                    "doctype": "User",
                    "docname": "user-001",
                    "field_name": "description",
                    "content": "User permissions can be configured through the Role Permission Manager.",
                    "chunk_index": 1,
                    "total_chunks": 2,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "source_url": "https://frappe.local/app/user/user-001",
                    "content_length": 65,
                    "word_count": 10
                }
            ),
            SearchResult(
                id="doc2_field1_chunk1",
                score=0.87,
                payload={
                    "doctype": "Role",
                    "docname": "role-001",
                    "field_name": "description",
                    "content": "This role provides access to user management features.",
                    "chunk_index": 1,
                    "total_chunks": 1,
                    "timestamp": "2024-01-15T11:00:00Z",
                    "content_length": 52,
                    "word_count": 9
                }
            )
        ]
    
    @pytest.mark.asyncio
    async def test_search_basic_functionality(self, mock_query_service, sample_search_results):
        """Test basic search functionality"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # Perform search
        result = await mock_query_service.search(
            query="user permissions",
            top_k=5
        )
        
        # Verify result
        assert isinstance(result, SearchResponse)
        assert result.query == "user permissions"
        assert len(result.chunks) == 2
        assert result.total_results == 2
        assert result.processing_time_ms > 0
        
        # Verify first chunk
        first_chunk = result.chunks[0]
        assert first_chunk.id == "doc1_field1_chunk1"
        assert first_chunk.doctype == "User"
        assert first_chunk.docname == "user-001"
        assert first_chunk.score == 0.95
        assert "User permissions" in first_chunk.content
        
        # Verify service calls
        mock_query_service.embedding_service.generate_embedding.assert_called_once_with(
            "user permissions", use_cache=True
        )
        mock_query_service.qdrant_service.search_vectors.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, mock_query_service, sample_search_results):
        """Test search with filters"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # Perform search with filters
        filters = {"doctype": "User"}
        result = await mock_query_service.search(
            query="permissions",
            top_k=10,
            filters=filters
        )
        
        # Verify filters were passed to Qdrant
        mock_query_service.qdrant_service.search_vectors.assert_called_once_with(
            query_vector=[0.1] * 384,
            limit=10,
            score_threshold=0.0,
            filter_conditions=filters
        )
        
        assert result.filters_applied == filters
    
    @pytest.mark.asyncio
    async def test_search_with_score_threshold(self, mock_query_service, sample_search_results):
        """Test search with score threshold"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # Perform search with score threshold
        result = await mock_query_service.search(
            query="permissions",
            score_threshold=0.8
        )
        
        # Verify threshold was passed to Qdrant
        mock_query_service.qdrant_service.search_vectors.assert_called_once_with(
            query_vector=[0.1] * 384,
            limit=5,
            score_threshold=0.8,
            filter_conditions=None
        )
        
        assert result.score_threshold_used == 0.8
    
    @pytest.mark.asyncio
    async def test_search_input_validation(self, mock_query_service):
        """Test search input validation"""
        # Test empty query
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await mock_query_service.search("")
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await mock_query_service.search("   ")
        
        # Test query too long
        mock_query_service.max_query_length = 10
        with pytest.raises(ValueError, match="Query too long"):
            await mock_query_service.search("This is a very long query that exceeds the limit")
    
    @pytest.mark.asyncio
    async def test_search_top_k_limits(self, mock_query_service, sample_search_results):
        """Test top_k parameter limits"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # Test default top_k
        result = await mock_query_service.search("test query")
        mock_query_service.qdrant_service.search_vectors.assert_called_with(
            query_vector=[0.1] * 384,
            limit=5,  # default
            score_threshold=0.0,
            filter_conditions=None
        )
        
        # Test max top_k limit
        mock_query_service.max_top_k = 50
        result = await mock_query_service.search("test query", top_k=100)
        args, kwargs = mock_query_service.qdrant_service.search_vectors.call_args
        assert kwargs['limit'] == 50  # should be capped at max_top_k
    
    @pytest.mark.asyncio
    async def test_search_metadata_inclusion(self, mock_query_service, sample_search_results):
        """Test metadata inclusion in search results"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # Test with metadata
        result = await mock_query_service.search(
            query="test",
            include_metadata=True
        )
        
        chunk = result.chunks[0]
        assert chunk.chunk_index == 1
        assert chunk.total_chunks == 2
        assert chunk.timestamp is not None
        assert chunk.content_length == 65
        assert chunk.word_count == 10
        
        # Test without metadata
        result = await mock_query_service.search(
            query="test",
            include_metadata=False
        )
        
        chunk = result.chunks[0]
        assert chunk.chunk_index is None
        assert chunk.total_chunks is None
        assert chunk.timestamp is None
    
    @pytest.mark.asyncio
    async def test_search_caching(self, mock_query_service, sample_search_results):
        """Test result caching functionality"""
        # Enable caching
        mock_query_service.enable_result_caching = True
        
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        
        # First search - should hit services
        result1 = await mock_query_service.search("test query")
        assert mock_query_service.embedding_service.generate_embedding.call_count == 1
        assert mock_query_service.qdrant_service.search_vectors.call_count == 1
        
        # Second identical search - should hit cache
        result2 = await mock_query_service.search("test query")
        assert mock_query_service.embedding_service.generate_embedding.call_count == 1  # No additional calls
        assert mock_query_service.qdrant_service.search_vectors.call_count == 1  # No additional calls
        
        # Results should be identical
        assert result1.query == result2.query
        assert len(result1.chunks) == len(result2.chunks)
        
        # Cache stats should reflect hit
        assert mock_query_service.stats["cache_hits"] == 1
        assert mock_query_service.stats["cache_misses"] == 1
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, mock_query_service):
        """Test error handling in search"""
        # Test embedding service error
        mock_query_service.embedding_service.generate_embedding.side_effect = Exception("Embedding failed")
        
        with pytest.raises(Exception, match="Embedding failed"):
            await mock_query_service.search("test query")
        
        # Test Qdrant service error
        mock_query_service.embedding_service.generate_embedding.side_effect = None
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.side_effect = Exception("Search failed")
        
        with pytest.raises(Exception, match="Search failed"):
            await mock_query_service.search("test query")
    
    @pytest.mark.asyncio
    async def test_convert_search_results(self, mock_query_service, sample_search_results):
        """Test conversion of search results to response format"""
        # Test with metadata
        chunks = await mock_query_service._convert_search_results(
            sample_search_results, 
            include_metadata=True
        )
        
        assert len(chunks) == 2
        
        # Check first chunk
        chunk = chunks[0]
        assert isinstance(chunk, SearchResultChunk)
        assert chunk.id == "doc1_field1_chunk1"
        assert chunk.doctype == "User"
        assert chunk.score == 0.95
        assert chunk.chunk_index == 1
        assert chunk.timestamp is not None
        
        # Test without metadata
        chunks = await mock_query_service._convert_search_results(
            sample_search_results, 
            include_metadata=False
        )
        
        chunk = chunks[0]
        assert chunk.chunk_index is None
        assert chunk.timestamp is None
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, mock_query_service, sample_search_results):
        """Test statistics tracking"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = sample_search_results
        mock_query_service.qdrant_service.get_collection_info.return_value = {"points_count": 1000}
        
        # Initial stats
        initial_queries = mock_query_service.stats["total_queries"]
        
        # Perform search
        await mock_query_service.search("test query")
        
        # Check stats updated
        assert mock_query_service.stats["total_queries"] == initial_queries + 1
        assert mock_query_service.stats["avg_processing_time_ms"] > 0
        assert mock_query_service.stats["avg_embedding_time_ms"] > 0
        assert mock_query_service.stats["avg_search_time_ms"] > 0
        
        # Get stats
        stats = await mock_query_service.get_stats()
        assert stats["total_queries"] == initial_queries + 1
        assert stats["vector_db_points_count"] == 1000
        assert stats["service_ready"] is True
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_query_service):
        """Test health check functionality"""
        # Setup mocks
        mock_query_service.qdrant_service.get_collection_info.return_value = {"points_count": 500}
        
        # Perform health check
        health = await mock_query_service.health_check()
        
        assert health["status"] == "healthy"
        assert health["embedding_service_ready"] is True
        assert health["vector_db_ready"] is True
        assert health["vector_db_points_count"] == 500
        assert "timestamp" in health
        
        # Test unhealthy state
        mock_query_service._ready = False
        health = await mock_query_service.health_check()
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    @pytest.mark.asyncio
    async def test_cache_management(self, mock_query_service):
        """Test cache management operations"""
        # Add some items to cache
        mock_query_service.result_cache = {"key1": {"result": "data1", "timestamp": 123}}
        
        # Clear cache
        result = await mock_query_service.clear_cache()
        
        assert result["result_cache_cleared"] == 1
        assert result["embedding_cache_cleared"] == 10  # From mock
        assert len(mock_query_service.result_cache) == 0
    
    def test_cache_key_generation(self, mock_query_service):
        """Test cache key generation"""
        # Same parameters should generate same key
        key1 = mock_query_service._get_cache_key("test", 5, 0.7, {"doctype": "User"})
        key2 = mock_query_service._get_cache_key("test", 5, 0.7, {"doctype": "User"})
        assert key1 == key2
        
        # Different parameters should generate different keys
        key3 = mock_query_service._get_cache_key("test", 10, 0.7, {"doctype": "User"})
        assert key1 != key3
        
        key4 = mock_query_service._get_cache_key("different", 5, 0.7, {"doctype": "User"})
        assert key1 != key4
    
    def test_service_ready_check(self, mock_query_service):
        """Test service readiness checks"""
        # All ready
        assert mock_query_service.is_ready() is True
        
        # Embedding service not ready
        mock_query_service.embedding_service.is_ready.return_value = False
        assert mock_query_service.is_ready() is False
        
        # Qdrant service not ready
        mock_query_service.embedding_service.is_ready.return_value = True
        mock_query_service.qdrant_service.is_ready.return_value = False
        assert mock_query_service.is_ready() is False
        
        # Service not initialized
        mock_query_service.qdrant_service.is_ready.return_value = True
        mock_query_service._ready = False
        assert mock_query_service.is_ready() is False