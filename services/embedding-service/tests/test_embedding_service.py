"""
Unit tests for the embedding service
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock sentence_transformers before importing our service
sys.modules['sentence_transformers'] = Mock()
sys.modules['torch'] = Mock()
sys.modules['numpy'] = Mock()

import numpy as np
from services.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test cases for EmbeddingService"""
    
    @pytest.fixture
    async def embedding_service(self):
        """Create a mock embedding service for testing"""
        service = EmbeddingService()
        
        # Mock the model loading
        with patch.object(service, '_load_model') as mock_load:
            mock_model = Mock()
            mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3, 0.4]])
            mock_load.return_value = mock_model
            
            await service.initialize()
            
        return service
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization"""
        service = EmbeddingService()
        
        with patch.object(service, '_load_model') as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model
            
            await service.initialize()
            
            assert service.is_ready()
            assert service.is_model_loaded()
            mock_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, embedding_service):
        """Test generating a single embedding"""
        text = "This is a test sentence."
        
        embedding = await embedding_service.generate_embedding(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 4  # Based on our mock
        assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.asyncio
    async def test_embedding_caching(self, embedding_service):
        """Test embedding caching functionality"""
        text = "This is a test sentence."
        
        # First call should generate embedding
        embedding1 = await embedding_service.generate_embedding(text, use_cache=True)
        
        # Second call should use cache
        embedding2 = await embedding_service.generate_embedding(text, use_cache=True)
        
        assert embedding1 == embedding2
        assert embedding_service.get_cache_size() == 1
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self, embedding_service):
        """Test embedding generation with cache disabled"""
        text = "This is a test sentence."
        
        # Generate embedding without caching
        embedding = await embedding_service.generate_embedding(text, use_cache=False)
        
        assert isinstance(embedding, list)
        assert embedding_service.get_cache_size() == 0
    
    @pytest.mark.asyncio
    async def test_batch_embedding_generation(self, embedding_service):
        """Test batch embedding generation"""
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        
        # Mock batch encoding
        with patch.object(embedding_service.model, 'encode') as mock_encode:
            mock_encode.return_value = np.array([
                [0.1, 0.2, 0.3, 0.4],
                [0.5, 0.6, 0.7, 0.8],
                [0.9, 1.0, 1.1, 1.2]
            ])
            
            embeddings = await embedding_service.generate_batch_embeddings(texts)
            
            assert len(embeddings) == 3
            assert all(len(emb) == 4 for emb in embeddings)
            assert all(isinstance(emb, list) for emb in embeddings)
    
    @pytest.mark.asyncio
    async def test_batch_with_cache(self, embedding_service):
        """Test batch generation with partial caching"""
        texts = [
            "Cached sentence.",
            "New sentence.",
            "Another new sentence."
        ]
        
        # Pre-cache one embedding
        cached_embedding = [0.1, 0.2, 0.3, 0.4]
        embedding_service._add_to_cache(texts[0], cached_embedding)
        
        # Mock batch encoding for new texts
        with patch.object(embedding_service.model, 'encode') as mock_encode:
            mock_encode.return_value = np.array([
                [0.5, 0.6, 0.7, 0.8],
                [0.9, 1.0, 1.1, 1.2]
            ])
            
            embeddings = await embedding_service.generate_batch_embeddings(texts)
            
            assert len(embeddings) == 3
            assert embeddings[0] == cached_embedding  # From cache
            assert embeddings[1] == [0.5, 0.6, 0.7, 0.8]  # New
            assert embeddings[2] == [0.9, 1.0, 1.1, 1.2]  # New
    
    @pytest.mark.asyncio
    async def test_empty_batch(self, embedding_service):
        """Test batch generation with empty input"""
        embeddings = await embedding_service.generate_batch_embeddings([])
        assert embeddings == []
    
    @pytest.mark.asyncio
    async def test_cache_size_limit(self, embedding_service):
        """Test cache size limiting"""
        # Set a small cache size for testing
        embedding_service.max_cache_size = 2
        
        texts = ["Text 1", "Text 2", "Text 3"]
        
        # Generate embeddings to fill cache beyond limit
        for text in texts:
            await embedding_service.generate_embedding(text, use_cache=True)
        
        # Cache should not exceed max size
        assert embedding_service.get_cache_size() <= 2
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, embedding_service):
        """Test cache key generation"""
        text1 = "Same text"
        text2 = "Same text"
        text3 = "Different text"
        
        key1 = embedding_service._get_cache_key(text1)
        key2 = embedding_service._get_cache_key(text2)
        key3 = embedding_service._get_cache_key(text3)
        
        assert key1 == key2  # Same text should have same key
        assert key1 != key3  # Different text should have different key
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, embedding_service):
        """Test cache clearing"""
        # Add some items to cache
        await embedding_service.generate_embedding("Test 1", use_cache=True)
        await embedding_service.generate_embedding("Test 2", use_cache=True)
        
        assert embedding_service.get_cache_size() > 0
        
        cleared_count = await embedding_service.clear_cache()
        
        assert embedding_service.get_cache_size() == 0
        assert cleared_count == 2
    
    @pytest.mark.asyncio
    async def test_service_not_ready_error(self):
        """Test error when service is not ready"""
        service = EmbeddingService()
        
        with pytest.raises(RuntimeError, match="Embedding service not ready"):
            await service.generate_embedding("Test text")
        
        with pytest.raises(RuntimeError, match="Embedding service not ready"):
            await service.generate_batch_embeddings(["Test text"])
    
    @pytest.mark.asyncio
    async def test_cleanup(self, embedding_service):
        """Test service cleanup"""
        # Add some cache entries
        await embedding_service.generate_embedding("Test", use_cache=True)
        
        assert embedding_service.is_ready()
        assert embedding_service.get_cache_size() > 0
        
        await embedding_service.cleanup()
        
        assert not embedding_service.is_ready()
        assert embedding_service.get_cache_size() == 0
        assert embedding_service.model is None
    
    def test_cache_operations(self, embedding_service):
        """Test direct cache operations"""
        text = "Test text"
        embedding = [0.1, 0.2, 0.3, 0.4]
        
        # Test adding to cache
        embedding_service._add_to_cache(text, embedding)
        assert embedding_service.get_cache_size() == 1
        
        # Test retrieving from cache
        retrieved = embedding_service._get_from_cache(text)
        assert retrieved == embedding
        
        # Test cache miss
        missing = embedding_service._get_from_cache("Non-existent text")
        assert missing is None