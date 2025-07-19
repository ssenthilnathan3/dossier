"""
Basic functionality tests for query service
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.query_service import QueryService


class TestBasicFunctionality:
    """Test basic query service functionality"""
    
    def test_service_instantiation(self):
        """Test that QueryService can be instantiated"""
        service = QueryService()
        assert service is not None
        assert hasattr(service, 'embedding_service')
        assert hasattr(service, 'qdrant_service')
        assert service.is_ready() is False  # Not initialized yet
    
    def test_service_configuration(self):
        """Test service configuration from environment"""
        service = QueryService()
        
        # Check default values
        assert service.default_top_k == 5
        assert service.max_top_k == 100
        assert service.default_score_threshold == 0.0
        assert service.max_query_length == 1000
        
        # Check cache configuration
        assert hasattr(service, 'result_cache')
        assert isinstance(service.result_cache, dict)
        assert len(service.result_cache) == 0
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        service = QueryService()
        
        # Same parameters should generate same key
        key1 = service._get_cache_key("test query", 5, 0.7, {"doctype": "User"})
        key2 = service._get_cache_key("test query", 5, 0.7, {"doctype": "User"})
        assert key1 == key2
        
        # Different parameters should generate different keys
        key3 = service._get_cache_key("test query", 10, 0.7, {"doctype": "User"})
        assert key1 != key3
        
        key4 = service._get_cache_key("different query", 5, 0.7, {"doctype": "User"})
        assert key1 != key4
        
        key5 = service._get_cache_key("test query", 5, 0.8, {"doctype": "User"})
        assert key1 != key5
        
        key6 = service._get_cache_key("test query", 5, 0.7, {"doctype": "Role"})
        assert key1 != key6
    
    def test_cache_validity_check(self):
        """Test cache validity checking"""
        service = QueryService()
        
        import time
        
        # Valid cache entry (recent)
        valid_entry = {"timestamp": time.time() - 100}  # 100 seconds ago
        assert service._is_cache_valid(valid_entry) is True
        
        # Invalid cache entry (old)
        invalid_entry = {"timestamp": time.time() - 400}  # 400 seconds ago (> 300 TTL)
        assert service._is_cache_valid(invalid_entry) is False
        
        # Disable caching
        service.enable_result_caching = False
        assert service._is_cache_valid(valid_entry) is False
    
    @pytest.mark.asyncio
    async def test_search_input_validation(self):
        """Test search input validation"""
        service = QueryService()
        
        # Mock dependencies to avoid initialization
        service.embedding_service = Mock()
        service.qdrant_service = Mock()
        service._ready = True
        
        # Test empty query
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await service.search("")
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await service.search("   ")
        
        # Test query too long
        service.max_query_length = 10
        with pytest.raises(ValueError, match="Query too long"):
            await service.search("This is a very long query that exceeds the limit")
    
    def test_top_k_parameter_handling(self):
        """Test top_k parameter validation and limits"""
        service = QueryService()
        
        # Test default values
        assert service.default_top_k == 5
        assert service.max_top_k == 100
        
        # Test that max_top_k is enforced (this would be tested in the search method)
        # For now, just verify the configuration is correct
        assert service.max_top_k >= service.default_top_k
    
    def test_statistics_initialization(self):
        """Test that statistics are properly initialized"""
        service = QueryService()
        
        expected_stats = [
            "total_queries",
            "cache_hits", 
            "cache_misses",
            "avg_processing_time_ms",
            "avg_embedding_time_ms",
            "avg_search_time_ms"
        ]
        
        for stat in expected_stats:
            assert stat in service.stats
            assert isinstance(service.stats[stat], (int, float))
        
        # Initial values should be zero
        assert service.stats["total_queries"] == 0
        assert service.stats["cache_hits"] == 0
        assert service.stats["cache_misses"] == 0
    
    def test_stats_update_method(self):
        """Test statistics update functionality"""
        service = QueryService()
        
        # Initial state
        assert service.stats["total_queries"] == 0
        assert service.stats["avg_processing_time_ms"] == 0.0
        
        # Update stats
        service._update_stats(100.0, 30.0, 70.0)
        
        # Check updates
        assert service.stats["total_queries"] == 1
        assert service.stats["avg_processing_time_ms"] == 100.0
        assert service.stats["avg_embedding_time_ms"] == 30.0
        assert service.stats["avg_search_time_ms"] == 70.0
        
        # Update again to test averaging
        service._update_stats(200.0, 40.0, 160.0)
        
        assert service.stats["total_queries"] == 2
        assert service.stats["avg_processing_time_ms"] == 150.0  # (100 + 200) / 2
        assert service.stats["avg_embedding_time_ms"] == 35.0   # (30 + 40) / 2
        assert service.stats["avg_search_time_ms"] == 115.0     # (70 + 160) / 2
    
    @pytest.mark.asyncio
    async def test_mocked_search_functionality(self):
        """Test search with fully mocked dependencies"""
        service = QueryService()
        
        # Mock embedding service
        service.embedding_service = Mock()
        service.embedding_service.is_ready.return_value = True
        service.embedding_service.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        
        # Mock Qdrant service
        service.qdrant_service = Mock()
        service.qdrant_service.is_ready.return_value = True
        
        # Create mock search results
        class MockSearchResult:
            def __init__(self, id, score, payload):
                self.id = id
                self.score = score
                self.payload = payload
        
        mock_results = [
            MockSearchResult(
                id="test_id_1",
                score=0.95,
                payload={
                    "doctype": "User",
                    "docname": "user-001", 
                    "field_name": "description",
                    "content": "Test content for user permissions",
                    "chunk_index": 1,
                    "total_chunks": 2,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "content_length": 30,
                    "word_count": 5
                }
            )
        ]
        
        service.qdrant_service.search_vectors = AsyncMock(return_value=mock_results)
        service._ready = True
        
        # Perform search
        result = await service.search("test query")
        
        # Verify result structure
        assert hasattr(result, 'query')
        assert hasattr(result, 'chunks')
        assert hasattr(result, 'total_results')
        assert hasattr(result, 'processing_time_ms')
        
        assert result.query == "test query"
        assert len(result.chunks) == 1
        assert result.total_results == 1
        assert result.processing_time_ms > 0
        
        # Verify chunk structure
        chunk = result.chunks[0]
        assert chunk.id == "test_id_1"
        assert chunk.doctype == "User"
        assert chunk.docname == "user-001"
        assert chunk.score == 0.95
        assert "Test content" in chunk.content
        
        # Verify service calls
        service.embedding_service.generate_embedding.assert_called_once_with(
            "test query", use_cache=True
        )
        service.qdrant_service.search_vectors.assert_called_once()
        
        # Verify stats were updated
        assert service.stats["total_queries"] == 1
        assert service.stats["avg_processing_time_ms"] > 0
    
    @pytest.mark.asyncio 
    async def test_health_check_basic(self):
        """Test basic health check functionality"""
        service = QueryService()
        
        # Mock dependencies
        service.embedding_service = Mock()
        service.embedding_service.is_ready.return_value = True
        
        service.qdrant_service = Mock()
        service.qdrant_service.is_ready.return_value = True
        service.qdrant_service.get_collection_info = AsyncMock(return_value={"points_count": 100})
        
        service._ready = True
        
        # Perform health check
        health = await service.health_check()
        
        # Verify health response
        assert "status" in health
        assert "timestamp" in health
        assert "embedding_service_ready" in health
        assert "vector_db_ready" in health
        assert "cache_size" in health
        
        assert health["status"] == "healthy"
        assert health["embedding_service_ready"] is True
        assert health["vector_db_ready"] is True
        assert health["vector_db_points_count"] == 100
    
    @pytest.mark.asyncio
    async def test_cache_management(self):
        """Test cache management operations"""
        service = QueryService()
        
        # Mock embedding service for clear_cache
        service.embedding_service = Mock()
        service.embedding_service.clear_cache = AsyncMock(return_value=5)
        
        # Add some items to result cache
        service.result_cache = {
            "key1": {"result": "data1", "timestamp": 123},
            "key2": {"result": "data2", "timestamp": 456}
        }
        
        # Clear cache
        result = await service.clear_cache()
        
        # Verify results
        assert result["result_cache_cleared"] == 2
        assert result["embedding_cache_cleared"] == 5
        assert len(service.result_cache) == 0
        
        # Verify embedding service was called
        service.embedding_service.clear_cache.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])