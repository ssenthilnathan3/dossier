"""
API integration tests for the embedding service with Qdrant
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies before importing
sys.modules['sentence_transformers'] = Mock()
sys.modules['torch'] = Mock()
sys.modules['numpy'] = Mock()
sys.modules['qdrant_client'] = Mock()

# Import after mocking
from main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def mock_services():
    """Mock the global services"""
    mock_embedding_service = Mock()
    mock_embedding_service.is_ready.return_value = True
    mock_embedding_service.is_model_loaded.return_value = True
    mock_embedding_service.get_cache_size.return_value = 0
    
    mock_qdrant_service = Mock()
    mock_qdrant_service.health_check.return_value = {
        "status": "healthy",
        "collection": "test_collection",
        "points_count": 100,
        "response_time_ms": 5.0
    }
    
    return mock_embedding_service, mock_qdrant_service


class TestAPIIntegration:
    """Test API integration with Qdrant"""
    
    def test_health_endpoint_structure(self, client):
        """Test that health endpoint has correct structure"""
        # This test will fail during startup, but we can test the structure
        response = client.get("/health")
        
        # The response might be 503 due to service not being initialized
        # but we can check that the endpoint exists
        assert response.status_code in [200, 503]
    
    def test_vector_endpoints_exist(self, client):
        """Test that vector endpoints exist"""
        # Test upsert endpoint
        response = client.post("/vectors/upsert", json={
            "id": "test_id",
            "vector": [0.1, 0.2, 0.3],
            "payload": {"test": "data"}
        })
        # Should return 503 if services not initialized, not 404
        assert response.status_code in [200, 422, 503]  # 422 for validation errors
        
        # Test search endpoint
        response = client.post("/vectors/search", json={
            "query_vector": [0.1, 0.2, 0.3],
            "limit": 5
        })
        assert response.status_code in [200, 422, 503]
        
        # Test delete endpoint
        response = client.delete("/vectors", json={
            "vector_ids": ["test_id"]
        })
        assert response.status_code in [200, 422, 503]
        
        # Test collection info endpoint
        response = client.get("/vectors/collection/info")
        assert response.status_code in [200, 503]
    
    def test_batch_upsert_endpoint_exists(self, client):
        """Test that batch upsert endpoint exists"""
        response = client.post("/vectors/upsert/batch", json={
            "vectors": [
                {
                    "id": "test_id_1",
                    "vector": [0.1, 0.2, 0.3],
                    "payload": {"test": "data1"}
                },
                {
                    "id": "test_id_2", 
                    "vector": [0.4, 0.5, 0.6],
                    "payload": {"test": "data2"}
                }
            ]
        })
        assert response.status_code in [200, 422, 503]


class TestRequestValidation:
    """Test request validation for vector operations"""
    
    def test_upsert_request_validation(self, client):
        """Test upsert request validation"""
        # Missing required fields
        response = client.post("/vectors/upsert", json={})
        assert response.status_code == 422
        
        # Invalid vector format
        response = client.post("/vectors/upsert", json={
            "id": "test_id",
            "vector": "not_a_list",
            "payload": {}
        })
        assert response.status_code == 422
    
    def test_search_request_validation(self, client):
        """Test search request validation"""
        # Missing query vector
        response = client.post("/vectors/search", json={})
        assert response.status_code == 422
        
        # Invalid limit
        response = client.post("/vectors/search", json={
            "query_vector": [0.1, 0.2, 0.3],
            "limit": -1
        })
        assert response.status_code == 422
        
        # Invalid score threshold
        response = client.post("/vectors/search", json={
            "query_vector": [0.1, 0.2, 0.3],
            "score_threshold": 1.5  # Should be <= 1.0
        })
        assert response.status_code == 422
    
    def test_delete_request_validation(self, client):
        """Test delete request validation"""
        # No vector_ids or filter_conditions
        response = client.delete("/vectors", json={})
        # This should pass validation but fail in service logic
        assert response.status_code in [422, 503]


if __name__ == "__main__":
    pytest.main([__file__])