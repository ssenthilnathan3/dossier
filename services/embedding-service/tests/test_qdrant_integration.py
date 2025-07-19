"""
Integration tests for Qdrant vector database operations
"""

import pytest
import asyncio
import os
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from services.qdrant_service import QdrantService, VectorPoint, SearchResult
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse


@pytest.fixture
def qdrant_service():
    """Create a QdrantService instance for testing"""
    # Use test environment variables
    os.environ["QDRANT_HOST"] = "localhost"
    os.environ["QDRANT_PORT"] = "6333"
    os.environ["QDRANT_COLLECTION"] = "test_collection"
    os.environ["VECTOR_SIZE"] = "384"
    
    service = QdrantService()
    return service


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing"""
    client = MagicMock()
    
    # Mock collections response
    collections_response = MagicMock()
    collections_response.collections = []
    client.get_collections.return_value = collections_response
    
    # Mock collection creation
    client.create_collection.return_value = None
    client.create_payload_index.return_value = None
    
    # Mock collection info
    collection_info = MagicMock()
    collection_info.config.params.vectors.size = 384
    collection_info.config.params.vectors.distance.value = "Cosine"
    collection_info.points_count = 100
    collection_info.segments_count = 1
    collection_info.status.value = "green"
    client.get_collection.return_value = collection_info
    
    return client


@pytest.mark.asyncio
class TestQdrantServiceInitialization:
    """Test Qdrant service initialization"""
    
    async def test_initialization_success(self, qdrant_service, mock_qdrant_client):
        """Test successful initialization"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            assert qdrant_service.is_ready()
            assert qdrant_service.client is not None
    
    async def test_initialization_with_existing_collection(self, qdrant_service, mock_qdrant_client):
        """Test initialization when collection already exists"""
        # Mock existing collection
        collections_response = MagicMock()
        collection = MagicMock()
        collection.name = "test_collection"
        collections_response.collections = [collection]
        mock_qdrant_client.get_collections.return_value = collections_response
        
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            assert qdrant_service.is_ready()
            # Should not call create_collection
            mock_qdrant_client.create_collection.assert_not_called()
    
    async def test_initialization_connection_failure(self, qdrant_service):
        """Test initialization with connection failure"""
        with patch('services.qdrant_service.QdrantClient') as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.get_collections.side_effect = ConnectionError("Connection failed")
            
            with pytest.raises(ConnectionError):
                await qdrant_service.initialize()
            
            assert not qdrant_service.is_ready()


@pytest.mark.asyncio
class TestVectorOperations:
    """Test vector CRUD operations"""
    
    async def test_upsert_single_vector(self, qdrant_service, mock_qdrant_client):
        """Test upserting a single vector"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            vector_point = VectorPoint(
                id="test_id_1",
                vector=[0.1, 0.2, 0.3] * 128,  # 384 dimensions
                payload={"doctype": "Document", "docname": "DOC-001"}
            )
            
            result = await qdrant_service.upsert_vectors([vector_point])
            
            assert result is True
            mock_qdrant_client.upsert.assert_called_once()
    
    async def test_upsert_batch_vectors(self, qdrant_service, mock_qdrant_client):
        """Test upserting multiple vectors in batches"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            vectors = [
                VectorPoint(
                    id=f"test_id_{i}",
                    vector=[0.1 * i, 0.2 * i, 0.3 * i] * 128,
                    payload={"doctype": "Document", "docname": f"DOC-{i:03d}"}
                )
                for i in range(250)  # More than batch size
            ]
            
            result = await qdrant_service.upsert_vectors(vectors, batch_size=100)
            
            assert result is True
            # Should be called 3 times (100, 100, 50)
            assert mock_qdrant_client.upsert.call_count == 3
    
    async def test_upsert_empty_vectors(self, qdrant_service, mock_qdrant_client):
        """Test upserting empty vector list"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            result = await qdrant_service.upsert_vectors([])
            
            assert result is True
            mock_qdrant_client.upsert.assert_not_called()
    
    async def test_upsert_with_retry_on_failure(self, qdrant_service, mock_qdrant_client):
        """Test upsert with retry logic on failure"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            # First call fails, second succeeds
            mock_qdrant_client.upsert.side_effect = [
                ConnectionError("Temporary failure"),
                None
            ]
            
            vector_point = VectorPoint(
                id="test_id_1",
                vector=[0.1, 0.2, 0.3] * 128,
                payload={"doctype": "Document"}
            )
            
            result = await qdrant_service.upsert_vectors([vector_point])
            
            assert result is True
            assert mock_qdrant_client.upsert.call_count == 2


@pytest.mark.asyncio
class TestVectorSearch:
    """Test vector search operations"""
    
    async def test_search_vectors_basic(self, qdrant_service, mock_qdrant_client):
        """Test basic vector search"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            # Mock search results
            mock_point = MagicMock()
            mock_point.id = "test_id_1"
            mock_point.score = 0.95
            mock_point.payload = {"doctype": "Document", "docname": "DOC-001"}
            mock_qdrant_client.search.return_value = [mock_point]
            
            query_vector = [0.1, 0.2, 0.3] * 128
            results = await qdrant_service.search_vectors(query_vector, limit=5)
            
            assert len(results) == 1
            assert results[0].id == "test_id_1"
            assert results[0].score == 0.95
            assert results[0].payload["doctype"] == "Document"
            
            mock_qdrant_client.search.assert_called_once()
    
    async def test_search_vectors_with_filter(self, qdrant_service, mock_qdrant_client):
        """Test vector search with filter conditions"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            mock_qdrant_client.search.return_value = []
            
            query_vector = [0.1, 0.2, 0.3] * 128
            filter_conditions = {"doctype": "Document", "status": "Published"}
            
            results = await qdrant_service.search_vectors(
                query_vector,
                limit=10,
                filter_conditions=filter_conditions
            )
            
            assert len(results) == 0
            mock_qdrant_client.search.assert_called_once()
            
            # Verify filter was passed
            call_args = mock_qdrant_client.search.call_args
            assert call_args[0][2] is not None  # filter argument
    
    async def test_search_vectors_with_score_threshold(self, qdrant_service, mock_qdrant_client):
        """Test vector search with score threshold"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            # Mock results with different scores
            mock_points = []
            for i, score in enumerate([0.95, 0.85, 0.75, 0.65]):
                mock_point = MagicMock()
                mock_point.id = f"test_id_{i}"
                mock_point.score = score
                mock_point.payload = {"doctype": "Document"}
                mock_points.append(mock_point)
            
            mock_qdrant_client.search.return_value = mock_points
            
            query_vector = [0.1, 0.2, 0.3] * 128
            results = await qdrant_service.search_vectors(
                query_vector,
                limit=10,
                score_threshold=0.8
            )
            
            # Should only return results with score >= 0.8
            assert len(results) == 2
            assert all(result.score >= 0.8 for result in results)
    
    async def test_search_vectors_with_retry_on_failure(self, qdrant_service, mock_qdrant_client):
        """Test search with retry logic on failure"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            # First call fails, second succeeds
            mock_qdrant_client.search.side_effect = [
                ConnectionError("Temporary failure"),
                []
            ]
            
            query_vector = [0.1, 0.2, 0.3] * 128
            results = await qdrant_service.search_vectors(query_vector)
            
            assert len(results) == 0
            assert mock_qdrant_client.search.call_count == 2


@pytest.mark.asyncio
class TestVectorDeletion:
    """Test vector deletion operations"""
    
    async def test_delete_vectors_by_ids(self, qdrant_service, mock_qdrant_client):
        """Test deleting vectors by IDs"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            vector_ids = ["test_id_1", "test_id_2", "test_id_3"]
            result = await qdrant_service.delete_vectors(vector_ids=vector_ids)
            
            assert result is True
            mock_qdrant_client.delete.assert_called_once()
    
    async def test_delete_vectors_by_filter(self, qdrant_service, mock_qdrant_client):
        """Test deleting vectors by filter conditions"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            filter_conditions = {"doctype": "Document", "status": "Deleted"}
            result = await qdrant_service.delete_vectors(filter_conditions=filter_conditions)
            
            assert result is True
            mock_qdrant_client.delete.assert_called_once()
    
    async def test_delete_vectors_no_criteria(self, qdrant_service, mock_qdrant_client):
        """Test delete with no criteria raises error"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            with pytest.raises(ValueError, match="Must provide either vector_ids or filter_conditions"):
                await qdrant_service.delete_vectors()
    
    async def test_delete_vectors_with_retry_on_failure(self, qdrant_service, mock_qdrant_client):
        """Test delete with retry logic on failure"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            # First call fails, second succeeds
            mock_qdrant_client.delete.side_effect = [
                ConnectionError("Temporary failure"),
                None
            ]
            
            result = await qdrant_service.delete_vectors(vector_ids=["test_id_1"])
            
            assert result is True
            assert mock_qdrant_client.delete.call_count == 2


@pytest.mark.asyncio
class TestHealthAndInfo:
    """Test health check and collection info operations"""
    
    async def test_get_collection_info(self, qdrant_service, mock_qdrant_client):
        """Test getting collection information"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            info = await qdrant_service.get_collection_info()
            
            assert "vector_size" in info
            assert "points_count" in info
            assert "status" in info
            assert info["points_count"] == 100
    
    async def test_health_check_healthy(self, qdrant_service, mock_qdrant_client):
        """Test health check when service is healthy"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            health = await qdrant_service.health_check()
            
            assert health["status"] == "healthy"
            assert "collection" in health
            assert "points_count" in health
            assert "response_time_ms" in health
    
    async def test_health_check_not_ready(self, qdrant_service):
        """Test health check when service is not ready"""
        health = await qdrant_service.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    async def test_health_check_with_error(self, qdrant_service, mock_qdrant_client):
        """Test health check when collection info fails"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            mock_qdrant_client.get_collection.side_effect = Exception("Connection error")
            
            health = await qdrant_service.health_check()
            
            assert health["status"] == "unhealthy"
            assert "error" in health


@pytest.mark.asyncio
class TestFilterBuilding:
    """Test filter building functionality"""
    
    async def test_build_filter_single_value(self, qdrant_service):
        """Test building filter with single values"""
        conditions = {"doctype": "Document", "status": "Published"}
        filter_obj = qdrant_service._build_filter(conditions)
        
        assert filter_obj is not None
        assert len(filter_obj.must) == 2
    
    async def test_build_filter_multiple_values(self, qdrant_service):
        """Test building filter with multiple values (OR condition)"""
        conditions = {"doctype": ["Document", "Task"], "status": "Published"}
        filter_obj = qdrant_service._build_filter(conditions)
        
        assert filter_obj is not None
        assert len(filter_obj.must) == 2


@pytest.mark.asyncio
class TestCleanup:
    """Test cleanup operations"""
    
    async def test_cleanup(self, qdrant_service, mock_qdrant_client):
        """Test service cleanup"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            assert qdrant_service.is_ready()
            
            await qdrant_service.cleanup()
            
            assert not qdrant_service.is_ready()
            assert qdrant_service.client is None
            mock_qdrant_client.close.assert_called_once()
    
    async def test_cleanup_with_client_error(self, qdrant_service, mock_qdrant_client):
        """Test cleanup when client close fails"""
        with patch('services.qdrant_service.QdrantClient', return_value=mock_qdrant_client):
            await qdrant_service.initialize()
            
            mock_qdrant_client.close.side_effect = Exception("Close error")
            
            # Should not raise exception
            await qdrant_service.cleanup()
            
            assert not qdrant_service.is_ready()
            assert qdrant_service.client is None


if __name__ == "__main__":
    pytest.main([__file__])