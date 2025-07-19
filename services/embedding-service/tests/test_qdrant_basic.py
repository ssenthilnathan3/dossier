"""
Basic tests for Qdrant service structure and imports
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_qdrant_service_structure():
    """Test that QdrantService can be imported and has expected structure"""
    # Mock qdrant_client before importing
    with patch.dict('sys.modules', {
        'qdrant_client': Mock(),
        'qdrant_client.http': Mock(),
        'qdrant_client.http.models': Mock(),
        'qdrant_client.http.exceptions': Mock(),
        'backoff': Mock()
    }):
        from services.qdrant_service import QdrantService, VectorPoint, SearchResult
        
        # Test that classes can be instantiated
        service = QdrantService()
        
        # Test that service has expected attributes
        assert hasattr(service, 'host')
        assert hasattr(service, 'port')
        assert hasattr(service, 'collection_name')
        assert hasattr(service, 'vector_size')
        assert hasattr(service, 'client')
        assert hasattr(service, '_ready')
        
        # Test that service has expected methods
        assert hasattr(service, 'initialize')
        assert hasattr(service, 'is_ready')
        assert hasattr(service, 'upsert_vectors')
        assert hasattr(service, 'search_vectors')
        assert hasattr(service, 'delete_vectors')
        assert hasattr(service, 'health_check')
        assert hasattr(service, 'cleanup')
        
        # Test VectorPoint structure
        vector_point = VectorPoint(
            id="test_id",
            vector=[0.1, 0.2, 0.3],
            payload={"test": "data"}
        )
        assert vector_point.id == "test_id"
        assert vector_point.vector == [0.1, 0.2, 0.3]
        assert vector_point.payload == {"test": "data"}
        
        # Test SearchResult structure
        search_result = SearchResult(
            id="result_id",
            score=0.95,
            payload={"result": "data"}
        )
        assert search_result.id == "result_id"
        assert search_result.score == 0.95
        assert search_result.payload == {"result": "data"}


def test_qdrant_service_configuration():
    """Test QdrantService configuration from environment variables"""
    with patch.dict('sys.modules', {
        'qdrant_client': Mock(),
        'qdrant_client.http': Mock(),
        'qdrant_client.http.models': Mock(),
        'qdrant_client.http.exceptions': Mock(),
        'backoff': Mock()
    }):
        # Test with custom environment variables
        with patch.dict(os.environ, {
            'QDRANT_HOST': 'custom-host',
            'QDRANT_PORT': '9999',
            'QDRANT_COLLECTION': 'custom_collection',
            'VECTOR_SIZE': '512'
        }):
            from services.qdrant_service import QdrantService
            
            service = QdrantService()
            
            assert service.host == 'custom-host'
            assert service.port == 9999
            assert service.collection_name == 'custom_collection'
            assert service.vector_size == 512


def test_request_response_models():
    """Test that request and response models can be imported"""
    from models.requests import (
        VectorUpsertRequest, BatchVectorUpsertRequest, 
        VectorSearchRequest, VectorDeleteRequest
    )
    from models.responses import (
        VectorSearchResponse, VectorUpsertResponse, 
        VectorDeleteResponse, QdrantHealthResponse
    )
    
    # Test VectorUpsertRequest
    upsert_request = VectorUpsertRequest(
        id="test_id",
        vector=[0.1, 0.2, 0.3],
        payload={"test": "data"}
    )
    assert upsert_request.id == "test_id"
    
    # Test VectorSearchRequest
    search_request = VectorSearchRequest(
        query_vector=[0.1, 0.2, 0.3],
        limit=10
    )
    assert search_request.query_vector == [0.1, 0.2, 0.3]
    assert search_request.limit == 10
    
    # Test VectorDeleteRequest
    delete_request = VectorDeleteRequest(
        vector_ids=["id1", "id2"]
    )
    assert delete_request.vector_ids == ["id1", "id2"]


if __name__ == "__main__":
    pytest.main([__file__])