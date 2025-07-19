"""
Basic tests for embedding service structure
"""

import pytest
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_service_structure():
    """Test that the service files exist and have basic structure"""
    # Test main.py exists
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
    assert os.path.exists(main_path)
    
    # Test services directory exists
    services_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services')
    assert os.path.exists(services_path)
    
    # Test models directory exists
    models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    assert os.path.exists(models_path)

def test_imports_without_dependencies():
    """Test that we can import basic structures"""
    # Test that we can read the service file
    service_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services', 'embedding_service.py')
    with open(service_path, 'r') as f:
        content = f.read()
        assert 'class EmbeddingService' in content
        assert 'async def generate_embedding' in content
        assert 'async def generate_batch_embeddings' in content

def test_model_files():
    """Test model files exist and have correct structure"""
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    
    # Test requests.py
    requests_path = os.path.join(models_dir, 'requests.py')
    assert os.path.exists(requests_path)
    with open(requests_path, 'r') as f:
        content = f.read()
        assert 'EmbeddingRequest' in content
        assert 'BatchEmbeddingRequest' in content
    
    # Test responses.py
    responses_path = os.path.join(models_dir, 'responses.py')
    assert os.path.exists(responses_path)
    with open(responses_path, 'r') as f:
        content = f.read()
        assert 'EmbeddingResponse' in content
        assert 'BatchEmbeddingResponse' in content
        assert 'HealthResponse' in content