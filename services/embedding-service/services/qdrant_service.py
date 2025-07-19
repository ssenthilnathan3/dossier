"""
Qdrant vector database service with connection management and retry logic
"""

import os
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
import backoff

logger = logging.getLogger(__name__)


@dataclass
class VectorPoint:
    """Represents a vector point with metadata"""
    id: str
    vector: List[float]
    payload: Dict[str, Any]


@dataclass
class SearchResult:
    """Represents a search result"""
    id: str
    score: float
    payload: Dict[str, Any]


class QdrantService:
    """Service for managing Qdrant vector database operations"""
    
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.api_key = os.getenv("QDRANT_API_KEY")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "dossier_embeddings")
        self.vector_size = int(os.getenv("VECTOR_SIZE", "384"))  # BGE-small dimension
        self.client: Optional[QdrantClient] = None
        self._ready = False
        
        # Connection settings
        self.max_retries = int(os.getenv("QDRANT_MAX_RETRIES", "5"))
        self.base_delay = float(os.getenv("QDRANT_BASE_DELAY", "1.0"))
        self.max_delay = float(os.getenv("QDRANT_MAX_DELAY", "60.0"))
        self.timeout = float(os.getenv("QDRANT_TIMEOUT", "30.0"))
    
    async def initialize(self):
        """Initialize Qdrant client and ensure collection exists"""
        try:
            logger.info(f"Connecting to Qdrant at {self.host}:{self.port}")
            
            # Create client
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key,
                timeout=self.timeout
            )
            
            # Test connection
            await self._test_connection()
            
            # Ensure collection exists
            await self._ensure_collection_exists()
            
            self._ready = True
            logger.info("Qdrant service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant service: {e}")
            raise
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, UnexpectedResponse, Exception),
        max_tries=5,
        base=1.0,
        max_value=60.0
    )
    async def _test_connection(self):
        """Test connection to Qdrant with retry logic"""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.get_collections)
            logger.info("Qdrant connection test successful")
        except Exception as e:
            logger.error(f"Qdrant connection test failed: {e}")
            raise
    
    async def _ensure_collection_exists(self):
        """Ensure the collection exists, create if it doesn't"""
        try:
            loop = asyncio.get_event_loop()
            
            # Check if collection exists
            collections = await loop.run_in_executor(None, self.client.get_collections)
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                
                # Create collection with vector configuration
                await loop.run_in_executor(
                    None,
                    self.client.create_collection,
                    self.collection_name,
                    models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Create payload indexes for efficient filtering
                await self._create_payload_indexes()
                
                logger.info(f"Collection {self.collection_name} created successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise
    
    async def _create_payload_indexes(self):
        """Create indexes on payload fields for efficient filtering"""
        try:
            loop = asyncio.get_event_loop()
            
            # Index common metadata fields
            indexes = [
                ("doctype", models.PayloadSchemaType.KEYWORD),
                ("docname", models.PayloadSchemaType.KEYWORD),
                ("field_name", models.PayloadSchemaType.KEYWORD),
                ("chunk_index", models.PayloadSchemaType.INTEGER)
            ]
            
            for field_name, field_type in indexes:
                await loop.run_in_executor(
                    None,
                    self.client.create_payload_index,
                    self.collection_name,
                    field_name,
                    field_type
                )
                logger.debug(f"Created index for field: {field_name}")
                
        except Exception as e:
            logger.warning(f"Error creating payload indexes: {e}")
            # Don't fail initialization if indexes can't be created
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self._ready and self.client is not None
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, UnexpectedResponse, Exception),
        max_tries=5,
        base=1.0,
        max_value=60.0
    )
    async def upsert_vectors(
        self, 
        vectors: List[VectorPoint],
        batch_size: int = 100
    ) -> bool:
        """Insert or update vectors in batches with retry logic"""
        if not self.is_ready():
            raise RuntimeError("Qdrant service not ready")
        
        if not vectors:
            return True
        
        try:
            loop = asyncio.get_event_loop()
            
            # Process in batches
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                
                # Convert to Qdrant points
                points = [
                    models.PointStruct(
                        id=vector.id,
                        vector=vector.vector,
                        payload=vector.payload
                    )
                    for vector in batch
                ]
                
                # Upsert batch
                await loop.run_in_executor(
                    None,
                    self.client.upsert,
                    self.collection_name,
                    points
                )
                
                logger.debug(f"Upserted batch {i//batch_size + 1}, {len(batch)} vectors")
            
            logger.info(f"Successfully upserted {len(vectors)} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting vectors: {e}")
            raise
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, UnexpectedResponse, Exception),
        max_tries=5,
        base=1.0,
        max_value=60.0
    )
    async def search_vectors(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar vectors with optional filtering"""
        if not self.is_ready():
            raise RuntimeError("Qdrant service not ready")
        
        try:
            loop = asyncio.get_event_loop()
            
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                query_filter = self._build_filter(filter_conditions)
            
            # Perform search
            search_result = await loop.run_in_executor(
                None,
                self.client.search,
                self.collection_name,
                query_vector,
                query_filter,
                limit,
                True,  # with_payload
                True   # with_vectors
            )
            
            # Convert results
            results = []
            for point in search_result:
                if score_threshold is None or point.score >= score_threshold:
                    results.append(SearchResult(
                        id=str(point.id),
                        score=point.score,
                        payload=point.payload or {}
                    ))
            
            logger.debug(f"Found {len(results)} similar vectors")
            return results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise
    
    def _build_filter(self, conditions: Dict[str, Any]) -> models.Filter:
        """Build Qdrant filter from conditions"""
        must_conditions = []
        
        for field, value in conditions.items():
            if isinstance(value, list):
                # Multiple values - use should (OR)
                should_conditions = [
                    models.FieldCondition(
                        key=field,
                        match=models.MatchValue(value=v)
                    ) for v in value
                ]
                must_conditions.append(
                    models.Filter(should=should_conditions)
                )
            else:
                # Single value - use must (AND)
                must_conditions.append(
                    models.FieldCondition(
                        key=field,
                        match=models.MatchValue(value=value)
                    )
                )
        
        return models.Filter(must=must_conditions)
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, UnexpectedResponse, Exception),
        max_tries=5,
        base=1.0,
        max_value=60.0
    )
    async def delete_vectors(
        self,
        vector_ids: List[str] = None,
        filter_conditions: Dict[str, Any] = None
    ) -> bool:
        """Delete vectors by IDs or filter conditions"""
        if not self.is_ready():
            raise RuntimeError("Qdrant service not ready")
        
        if not vector_ids and not filter_conditions:
            raise ValueError("Must provide either vector_ids or filter_conditions")
        
        try:
            loop = asyncio.get_event_loop()
            
            if vector_ids:
                # Delete by IDs
                points_selector = models.PointIdsList(points=vector_ids)
                await loop.run_in_executor(
                    None,
                    lambda: self.client.delete(
                        collection_name=self.collection_name,
                        points_selector=points_selector
                    )
                )
                logger.info(f"Deleted {len(vector_ids)} vectors by ID")
            
            if filter_conditions:
                # Delete by filter
                query_filter = self._build_filter(filter_conditions)
                points_selector = models.FilterSelector(filter=query_filter)
                await loop.run_in_executor(
                    None,
                    lambda: self.client.delete(
                        collection_name=self.collection_name,
                        points_selector=points_selector
                    )
                )
                logger.info(f"Deleted vectors matching filter: {filter_conditions}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            raise
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, UnexpectedResponse, Exception),
        max_tries=3,
        base=1.0,
        max_value=30.0
    )
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        if not self.is_ready():
            raise RuntimeError("Qdrant service not ready")
        
        try:
            loop = asyncio.get_event_loop()
            
            collection_info = await loop.run_in_executor(
                None,
                self.client.get_collection,
                self.collection_name
            )
            
            return {
                "name": collection_info.config.params.vectors.size,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.value,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "status": collection_info.status.value
            }
            
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            if not self.is_ready():
                return {
                    "status": "unhealthy",
                    "error": "Service not ready"
                }
            
            # Test connection
            start_time = time.time()
            collection_info = await self.get_collection_info()
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "collection": self.collection_name,
                "points_count": collection_info["points_count"],
                "response_time_ms": round(response_time * 1000, 2)
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Qdrant service")
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error closing Qdrant client: {e}")
        
        self.client = None
        self._ready = False