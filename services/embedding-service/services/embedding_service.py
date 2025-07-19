"""
Core embedding service implementation using BGE-small model
"""

import os
import hashlib
import logging
import asyncio
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using BGE-small model"""
    
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        self.model: Optional[SentenceTransformer] = None
        self.cache: Dict[str, List[float]] = {}
        self.max_cache_size = int(os.getenv("EMBEDDING_CACHE_SIZE", "10000"))
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
        self._ready = False
        
    async def initialize(self):
        """Initialize the embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            
            # Load model in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, 
                self._load_model
            )
            
            self._ready = True
            logger.info("Embedding model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise
    
    def _load_model(self) -> SentenceTransformer:
        """Load the sentence transformer model"""
        return SentenceTransformer(
            self.model_name,
            device='cpu'  # Use CPU for better compatibility
        )
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self._ready and self.model is not None
    
    def is_model_loaded(self) -> bool:
        """Check if the model is loaded"""
        return self.model is not None
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _add_to_cache(self, text: str, embedding: List[float]):
        """Add embedding to cache with LRU eviction"""
        if len(self.cache) >= self.max_cache_size:
            # Remove oldest entry (simple FIFO for now)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        cache_key = self._get_cache_key(text)
        self.cache[cache_key] = embedding
    
    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        cache_key = self._get_cache_key(text)
        return self.cache.get(cache_key)
    
    async def generate_embedding(
        self, 
        text: str, 
        use_cache: bool = True
    ) -> List[float]:
        """Generate embedding for a single text"""
        if not self.is_ready():
            raise RuntimeError("Embedding service not ready")
        
        # Check cache first
        if use_cache:
            cached_embedding = self._get_from_cache(text)
            if cached_embedding is not None:
                logger.debug("Retrieved embedding from cache")
                return cached_embedding
        
        try:
            # Generate embedding
            loop = asyncio.get_event_loop()
            embedding_array = await loop.run_in_executor(
                None,
                self._generate_single_embedding,
                text
            )
            
            # Convert to list
            embedding = embedding_array.tolist()
            
            # Cache the result
            if use_cache:
                self._add_to_cache(text, embedding)
            
            logger.debug(f"Generated embedding with dimension: {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            raise
    
    def _generate_single_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using the model (blocking operation)"""
        return self.model.encode([text], normalize_embeddings=True)[0]
    
    async def generate_batch_embeddings(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        use_cache: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not self.is_ready():
            raise RuntimeError("Embedding service not ready")
        
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        embeddings = []
        
        # Check cache for existing embeddings
        cached_embeddings = {}
        texts_to_process = []
        text_indices = {}
        
        if use_cache:
            for i, text in enumerate(texts):
                cached_embedding = self._get_from_cache(text)
                if cached_embedding is not None:
                    cached_embeddings[i] = cached_embedding
                else:
                    text_indices[len(texts_to_process)] = i
                    texts_to_process.append(text)
        else:
            texts_to_process = texts
            text_indices = {i: i for i in range(len(texts))}
        
        logger.info(f"Processing {len(texts_to_process)} texts, {len(cached_embeddings)} from cache")
        
        # Process texts in batches
        new_embeddings = []
        for i in range(0, len(texts_to_process), batch_size):
            batch_texts = texts_to_process[i:i + batch_size]
            
            try:
                # Generate embeddings for batch
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    None,
                    self._generate_batch_embeddings,
                    batch_texts
                )
                
                new_embeddings.extend(batch_embeddings)
                
                # Cache new embeddings
                if use_cache:
                    for text, embedding in zip(batch_texts, batch_embeddings):
                        self._add_to_cache(text, embedding)
                
                logger.debug(f"Processed batch {i//batch_size + 1}, generated {len(batch_embeddings)} embeddings")
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                raise
        
        # Combine cached and new embeddings in original order
        result_embeddings = [None] * len(texts)
        
        # Add cached embeddings
        for original_idx, embedding in cached_embeddings.items():
            result_embeddings[original_idx] = embedding
        
        # Add new embeddings
        for new_idx, embedding in enumerate(new_embeddings):
            original_idx = text_indices[new_idx]
            result_embeddings[original_idx] = embedding
        
        return result_embeddings
    
    def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts (blocking operation)"""
        embeddings_array = self.model.encode(texts, normalize_embeddings=True)
        return [embedding.tolist() for embedding in embeddings_array]
    
    async def clear_cache(self) -> int:
        """Clear the embedding cache"""
        cache_size = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared embedding cache, removed {cache_size} entries")
        return cache_size
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up embedding service")
        self.cache.clear()
        self.model = None
        self._ready = False