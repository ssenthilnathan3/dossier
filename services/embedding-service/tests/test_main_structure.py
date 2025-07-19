"""
Test main application structure and endpoint definitions
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_main_app_structure():
    """Test that main app can be imported and has expected endpoints"""
    # Mock all dependencies
    with patch.dict('sys.modules', {
        'sentence_transformers': Mock(),
        'torch': Mock(),
        'numpy': Mock(),
        'qdrant_client': Mock(),
        'qdrant_client.http': Mock(),
        'qdrant_client.http.models': Mock(),
        'qdrant_client.http.exceptions': Mock(),
        'backoff': Mock()
    }):
        from main import app
        
        # Test that app is a FastAPI instance
        assert hasattr(app, 'routes')
        assert hasattr(app, 'title')
        assert app.title == "Dossier Embedding Service"
        
        # Get all route paths
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Test that expected endpoints exist
        expected_endpoints = [
            '/health',
            '/embed',
            '/embed/batch',
            '/cache',
            '/vectors/upsert',
            '/vectors/upsert/batch',
            '/vectors/search',
            '/vectors',
            '/vectors/collection/info'
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in route_paths, f"Endpoint {endpoint} not found in routes"


def test_endpoint_methods():
    """Test that endpoints have correct HTTP methods"""
    with patch.dict('sys.modules', {
        'sentence_transformers': Mock(),
        'torch': Mock(),
        'numpy': Mock(),
        'qdrant_client': Mock(),
        'qdrant_client.http': Mock(),
        'qdrant_client.http.models': Mock(),
        'qdrant_client.http.exceptions': Mock(),
        'backoff': Mock()
    }):
        from main import app
        
        # Create a mapping of path to expected methods
        expected_methods = {
            '/health': ['GET'],
            '/embed': ['POST'],
            '/embed/batch': ['POST'],
            '/cache': ['DELETE'],
            '/vectors/upsert': ['POST'],
            '/vectors/upsert/batch': ['POST'],
            '/vectors/search': ['POST'],
            '/vectors': ['DELETE'],
            '/vectors/collection/info': ['GET']
        }
        
        # Check each route
        for route in app.routes:
            if hasattr(route, 'path') and route.path in expected_methods:
                route_methods = list(route.methods) if hasattr(route, 'methods') else []
                expected = expected_methods[route.path]
                
                for method in expected:
                    assert method in route_methods, f"Method {method} not found for {route.path}"


if __name__ == "__main__":
    pytest.main([__file__])