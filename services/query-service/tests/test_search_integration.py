"""
Integration tests for complete search workflows
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.query_service import QueryService

# Import response models
try:
    from models.responses import SearchResponse, SearchResultChunk
except ImportError:
    # For testing, import directly
    import sys
    models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    sys.path.insert(0, models_path)
    from responses import SearchResponse, SearchResultChunk


class TestSearchIntegration:
    """Integration tests for search workflows"""
    
    @pytest.fixture
    def mock_query_service(self):
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
    def comprehensive_search_results(self):
        """Comprehensive search results for testing"""
        class MockSearchResult:
            def __init__(self, id, score, payload):
                self.id = id
                self.score = score
                self.payload = payload
        
        return [
            MockSearchResult(
                id="user_doc_1_chunk_1",
                score=0.95,
                payload={
                    "doctype": "User",
                    "docname": "admin-user",
                    "field_name": "description",
                    "content": "Administrator user with full system permissions and access control management.",
                    "chunk_index": 1,
                    "total_chunks": 2,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "source_url": "https://frappe.local/app/user/admin-user",
                    "content_length": 78,
                    "word_count": 11
                }
            ),
            MockSearchResult(
                id="role_doc_1_chunk_1",
                score=0.87,
                payload={
                    "doctype": "Role",
                    "docname": "system-manager",
                    "field_name": "description",
                    "content": "System Manager role provides comprehensive access to system configuration and user management.",
                    "chunk_index": 1,
                    "total_chunks": 1,
                    "timestamp": "2024-01-15T11:00:00Z",
                    "source_url": "https://frappe.local/app/role/system-manager",
                    "content_length": 95,
                    "word_count": 13
                }
            ),
            MockSearchResult(
                id="permission_doc_1_chunk_1",
                score=0.82,
                payload={
                    "doctype": "Custom DocPerm",
                    "docname": "user-permissions",
                    "field_name": "description",
                    "content": "Custom document permissions for user access control and data security.",
                    "chunk_index": 1,
                    "total_chunks": 3,
                    "timestamp": "2024-01-15T12:00:00Z",
                    "content_length": 72,
                    "word_count": 10
                }
            )
        ]
    
    @pytest.mark.asyncio
    async def test_complete_search_workflow_with_results(self, mock_query_service, comprehensive_search_results):
        """Test complete search workflow with results"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        mock_query_service.qdrant_service.get_collection_info.return_value = {"points_count": 1500}
        
        # Perform search
        result = await mock_query_service.search(
            query="user permissions and access control",
            top_k=10,
            score_threshold=0.7,
            filters={"doctype": ["User", "Role"]},
            include_metadata=True
        )
        
        # Verify response structure
        assert hasattr(result, 'query')
        assert hasattr(result, 'chunks')
        assert hasattr(result, 'total_results')
        assert result.query == "user permissions and access control"
        assert len(result.chunks) == 3
        assert result.total_results == 3
        assert result.processing_time_ms > 0
        assert result.embedding_time_ms > 0
        assert result.search_time_ms > 0
        assert result.filters_applied == {"doctype": ["User", "Role"]}
        assert result.score_threshold_used == 0.7
        
        # Verify chunks are sorted by score (highest first)
        scores = [chunk.score for chunk in result.chunks]
        assert scores == sorted(scores, reverse=True)
        
        # Verify first chunk (highest score)
        first_chunk = result.chunks[0]
        assert first_chunk.id == "user_doc_1_chunk_1"
        assert first_chunk.doctype == "User"
        assert first_chunk.docname == "admin-user"
        assert first_chunk.score == 0.95
        assert "Administrator user" in first_chunk.content
        assert first_chunk.chunk_index == 1
        assert first_chunk.total_chunks == 2
        assert first_chunk.timestamp is not None
        assert first_chunk.source_url == "https://frappe.local/app/user/admin-user"
        
        # Verify analytics were updated
        assert mock_query_service.stats["total_queries"] == 1
        assert mock_query_service.stats["avg_processing_time_ms"] > 0
        assert mock_query_service.stats["avg_results_per_query"] == 3.0
        assert mock_query_service.stats["filtered_results_count"] == 1
        assert "User" in mock_query_service.stats["top_doctypes"]
        assert "Role" in mock_query_service.stats["top_doctypes"]
        
        # Verify query length stats
        query_length = len("user permissions and access control")
        assert mock_query_service.stats["query_length_stats"]["min"] == query_length
        assert mock_query_service.stats["query_length_stats"]["max"] == query_length
        assert mock_query_service.stats["query_length_stats"]["avg"] == query_length
    
    @pytest.mark.asyncio
    async def test_empty_results_workflow(self, mock_query_service):
        """Test workflow when no results are found"""
        # Setup mocks for empty results
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = []
        
        # Perform search
        result = await mock_query_service.search(
            query="nonexistent document type",
            top_k=5,
            score_threshold=0.8,
            filters={"doctype": "NonExistent"}
        )
        
        # Verify empty response
        assert hasattr(result, 'query')
        assert hasattr(result, 'chunks')
        assert hasattr(result, 'total_results')
        assert result.query == "nonexistent document type"
        assert len(result.chunks) == 0
        assert result.total_results == 0
        assert result.processing_time_ms > 0
        assert result.filters_applied == {"doctype": "NonExistent"}
        assert result.score_threshold_used == 0.8
        
        # Verify empty results were tracked
        assert mock_query_service.stats["empty_results_count"] == 1
        assert mock_query_service.stats["total_queries"] == 1
        assert mock_query_service.stats["avg_results_per_query"] == 0.0
    
    @pytest.mark.asyncio
    async def test_caching_workflow(self, mock_query_service, comprehensive_search_results):
        """Test search result caching workflow"""
        # Enable caching
        mock_query_service.enable_result_caching = True
        
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        
        query = "test caching query"
        
        # First search - should hit services
        result1 = await mock_query_service.search(query, top_k=5)
        
        # Verify service calls
        assert mock_query_service.embedding_service.generate_embedding.call_count == 1
        assert mock_query_service.qdrant_service.search_vectors.call_count == 1
        assert mock_query_service.stats["cache_misses"] == 1
        assert mock_query_service.stats["cache_hits"] == 0
        
        # Second identical search - should hit cache
        result2 = await mock_query_service.search(query, top_k=5)
        
        # Verify no additional service calls
        assert mock_query_service.embedding_service.generate_embedding.call_count == 1
        assert mock_query_service.qdrant_service.search_vectors.call_count == 1
        assert mock_query_service.stats["cache_misses"] == 1
        assert mock_query_service.stats["cache_hits"] == 1
        
        # Results should be identical
        assert result1.query == result2.query
        assert len(result1.chunks) == len(result2.chunks)
        assert result1.total_results == result2.total_results
        
        # Cache should contain the result
        assert len(mock_query_service.result_cache) == 1
    
    @pytest.mark.asyncio
    async def test_metadata_inclusion_workflow(self, mock_query_service, comprehensive_search_results):
        """Test metadata inclusion in search results"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        
        # Search with metadata
        result_with_metadata = await mock_query_service.search(
            query="test metadata",
            include_metadata=True
        )
        
        chunk = result_with_metadata.chunks[0]
        assert chunk.chunk_index == 1
        assert chunk.total_chunks == 2
        assert chunk.timestamp is not None
        assert chunk.source_url is not None
        assert chunk.content_length == 78
        assert chunk.word_count == 11
        
        # Search without metadata
        result_without_metadata = await mock_query_service.search(
            query="test metadata no meta",
            include_metadata=False
        )
        
        chunk = result_without_metadata.chunks[0]
        assert chunk.chunk_index is None
        assert chunk.total_chunks is None
        assert chunk.timestamp is None
        assert chunk.source_url is None
        assert chunk.content_length is None
        assert chunk.word_count is None
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mock_query_service):
        """Test error handling in search workflow"""
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
    async def test_analytics_and_logging_workflow(self, mock_query_service, comprehensive_search_results):
        """Test analytics and logging functionality"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        
        # Perform multiple searches to test analytics
        queries = [
            "short query",
            "this is a much longer query with many words to test length statistics",
            "medium length query here"
        ]
        
        for query in queries:
            await mock_query_service.search(query, top_k=5)
        
        # Verify analytics
        stats = mock_query_service.stats
        assert stats["total_queries"] == 3
        assert stats["query_length_stats"]["min"] == len("short query")
        assert stats["query_length_stats"]["max"] == len(queries[1])  # longest query
        assert stats["query_length_stats"]["avg"] > 0
        assert stats["avg_results_per_query"] == 3.0  # All queries returned 3 results
        
        # Verify doctype tracking
        assert stats["top_doctypes"]["User"] == 3  # 3 queries * 1 User result each
        assert stats["top_doctypes"]["Role"] == 3  # 3 queries * 1 Role result each
        assert stats["top_doctypes"]["Custom DocPerm"] == 3
    
    @pytest.mark.asyncio
    async def test_empty_result_suggestions(self, mock_query_service):
        """Test empty result suggestions functionality"""
        # Setup mocks for empty results
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = []
        
        # Test with filters
        suggestions_with_filters = mock_query_service._generate_empty_result_suggestions(
            "test query", {"doctype": "User"}
        )
        assert "Try removing or relaxing filters" in suggestions_with_filters
        
        # Test with very long query
        long_query = "a" * 150
        suggestions_long = mock_query_service._generate_empty_result_suggestions(long_query, None)
        assert "Try using a shorter, more specific query" in suggestions_long
        
        # Test with very short query
        suggestions_short = mock_query_service._generate_empty_result_suggestions("a", None)
        assert "Try adding more descriptive keywords" in suggestions_short
        
        # All suggestions should include spelling check
        for suggestions in [suggestions_with_filters, suggestions_long, suggestions_short]:
            assert "Check spelling and try synonyms" in suggestions
    
    @pytest.mark.asyncio
    async def test_result_enhancement_workflow(self, mock_query_service, comprehensive_search_results):
        """Test result enhancement functionality"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        
        # Perform search
        result = await mock_query_service.search("user permissions access")
        
        # Verify results are sorted by score
        scores = [chunk.score for chunk in result.chunks]
        assert scores == sorted(scores, reverse=True)
        
        # Verify query word overlap was calculated (internal enhancement)
        for chunk in result.chunks:
            # Check if internal metadata was added
            assert hasattr(chunk, '__dict__')
            # The _query_word_overlap should be set during enhancement
            if '_query_word_overlap' in chunk.__dict__:
                assert isinstance(chunk.__dict__['_query_word_overlap'], int)
                assert chunk.__dict__['_query_word_overlap'] >= 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_stats_workflow(self, mock_query_service, comprehensive_search_results):
        """Test comprehensive statistics collection"""
        # Setup mocks
        mock_query_service.embedding_service.generate_embedding.return_value = [0.1] * 384
        mock_query_service.qdrant_service.search_vectors.return_value = comprehensive_search_results
        mock_query_service.qdrant_service.get_collection_info.return_value = {"points_count": 2500}
        
        # Perform searches with different parameters
        await mock_query_service.search("query 1", filters={"doctype": "User"})
        await mock_query_service.search("query 2", filters={"doctype": "Role"})
        await mock_query_service.search("query 3")  # No filters
        
        # Get comprehensive stats
        stats = await mock_query_service.get_stats()
        
        # Verify all expected stats are present
        expected_keys = [
            "total_queries", "cache_hits", "cache_misses",
            "avg_processing_time_ms", "avg_embedding_time_ms", "avg_search_time_ms",
            "empty_results_count", "filtered_results_count", "top_doctypes",
            "avg_results_per_query", "query_length_stats",
            "cache_size", "embedding_cache_size", "vector_db_points_count",
            "service_ready", "embedding_service_ready", "vector_db_ready"
        ]
        
        for key in expected_keys:
            assert key in stats
        
        # Verify specific values
        assert stats["total_queries"] == 3
        assert stats["filtered_results_count"] == 2  # Two queries had filters
        assert stats["vector_db_points_count"] == 2500
        assert stats["service_ready"] is True
        assert stats["avg_results_per_query"] == 3.0
    
    @pytest.mark.asyncio
    async def test_health_check_workflow(self, mock_query_service):
        """Test comprehensive health check workflow"""
        # Setup mocks
        mock_query_service.qdrant_service.get_collection_info.return_value = {"points_count": 1000}
        
        # Perform health check
        health = await mock_query_service.health_check()
        
        # Verify health response structure
        expected_keys = [
            "status", "timestamp", "embedding_service_ready",
            "vector_db_ready", "cache_size", "vector_db_points_count"
        ]
        
        for key in expected_keys:
            assert key in health
        
        # Verify healthy state
        assert health["status"] == "healthy"
        assert health["embedding_service_ready"] is True
        assert health["vector_db_ready"] is True
        assert health["vector_db_points_count"] == 1000
        assert isinstance(health["timestamp"], datetime)
        
        # Test unhealthy state
        mock_query_service._ready = False
        health_unhealthy = await mock_query_service.health_check()
        assert health_unhealthy["status"] == "unhealthy"
        assert "error" in health_unhealthy


if __name__ == "__main__":
    pytest.main([__file__, "-v"])