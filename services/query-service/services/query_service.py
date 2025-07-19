"""
Core query service implementation for semantic search and retrieval
"""

import os
import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import embedding service components
import sys
import importlib.util

# Add paths for embedding service
embedding_service_path = os.path.join(os.path.dirname(__file__), '../../../embedding-service/services')
sys.path.insert(0, embedding_service_path)

try:
    from embedding_service import EmbeddingService
    from qdrant_service import QdrantService, SearchResult
except ImportError as e:
    print(f"Failed to import embedding service components: {e}")
    # For testing, create mock classes
    class EmbeddingService:
        def __init__(self): pass
        async def initialize(self): pass
        def is_ready(self): return True
        async def generate_embedding(self, text, use_cache=True): return [0.1] * 384
        def get_cache_size(self): return 0
        async def clear_cache(self): return 0
        async def cleanup(self): pass
    
    class QdrantService:
        def __init__(self): pass
        async def initialize(self): pass
        def is_ready(self): return True
        async def search_vectors(self, **kwargs): return []
        async def get_collection_info(self): return {"points_count": 0}
        async def cleanup(self): pass
    
    class SearchResult:
        def __init__(self, id, score, payload):
            self.id = id
            self.score = score
            self.payload = payload

# Import shared models
shared_models_path = os.path.join(os.path.dirname(__file__), '../../../../shared/models')
sys.path.insert(0, shared_models_path)

try:
    from document import DocumentChunk
except ImportError:
    # For testing, create mock class
    class DocumentChunk:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

# Import models - handle both relative and absolute imports
try:
    from ..models.responses import SearchResponse, SearchResultChunk
except ImportError:
    # For testing, import directly
    import sys
    models_path = os.path.join(os.path.dirname(__file__), '../models')
    sys.path.insert(0, models_path)
    from responses import SearchResponse, SearchResultChunk

logger = logging.getLogger(__name__)


class QueryService:
    """Service for handling semantic search queries"""
    
    def __init__(self):
        # Service dependencies
        self.embedding_service = EmbeddingService()
        self.qdrant_service = QdrantService()
        
        # Configuration
        self.default_top_k = int(os.getenv("DEFAULT_TOP_K", "5"))
        self.max_top_k = int(os.getenv("MAX_TOP_K", "100"))
        self.default_score_threshold = float(os.getenv("DEFAULT_SCORE_THRESHOLD", "0.0"))
        self.max_query_length = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
        
        # Performance settings
        self.enable_result_caching = os.getenv("ENABLE_RESULT_CACHING", "true").lower() == "true"
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes
        
        # Simple in-memory cache for results
        self.result_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics and analytics
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_processing_time_ms": 0.0,
            "avg_embedding_time_ms": 0.0,
            "avg_search_time_ms": 0.0,
            "empty_results_count": 0,
            "filtered_results_count": 0,
            "top_doctypes": {},
            "avg_results_per_query": 0.0,
            "query_length_stats": {
                "min": 0,
                "max": 0,
                "avg": 0.0
            }
        }
        
        self._ready = False
    
    async def initialize(self):
        """Initialize the query service and its dependencies"""
        try:
            logger.info("Initializing Query Service")
            
            # Initialize embedding service
            logger.info("Initializing embedding service...")
            await self.embedding_service.initialize()
            
            # Initialize Qdrant service
            logger.info("Initializing Qdrant service...")
            await self.qdrant_service.initialize()
            
            self._ready = True
            logger.info("Query Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Query Service: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return (
            self._ready and 
            self.embedding_service.is_ready() and 
            self.qdrant_service.is_ready()
        )
    
    def _get_cache_key(self, query: str, top_k: int, score_threshold: Optional[float], filters: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for query parameters"""
        import hashlib
        
        cache_data = {
            "query": query,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "filters": filters or {}
        }
        
        cache_str = str(sorted(cache_data.items()))
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        if not self.enable_result_caching:
            return False
        
        cache_time = cache_entry.get("timestamp", 0)
        return (time.time() - cache_time) < self.cache_ttl_seconds
    
    def _add_to_cache(self, cache_key: str, result: SearchResponse):
        """Add result to cache"""
        if not self.enable_result_caching:
            return
        
        self.result_cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
        
        # Simple cache cleanup - remove oldest entries if cache gets too large
        if len(self.result_cache) > 1000:  # Max 1000 cached results
            oldest_key = min(self.result_cache.keys(), key=lambda k: self.result_cache[k]["timestamp"])
            del self.result_cache[oldest_key]
    
    def _get_from_cache(self, cache_key: str) -> Optional[SearchResponse]:
        """Get result from cache if valid"""
        if not self.enable_result_caching:
            return None
        
        cache_entry = self.result_cache.get(cache_key)
        if cache_entry and self._is_cache_valid(cache_entry):
            return cache_entry["result"]
        
        # Remove invalid cache entry
        if cache_entry:
            del self.result_cache[cache_key]
        
        return None
    
    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> SearchResponse:
        """Perform semantic search with enhanced analytics and result processing"""
        start_time = time.time()
        query_cleaned = query.strip()
        
        # Validate inputs
        if not query or not query_cleaned:
            raise ValueError("Query cannot be empty")
        
        if len(query) > self.max_query_length:
            raise ValueError(f"Query too long (max {self.max_query_length} characters)")
        
        # Set defaults
        top_k = min(top_k or self.default_top_k, self.max_top_k)
        score_threshold = score_threshold or self.default_score_threshold
        
        # Log query analytics
        logger.info(f"Processing search query: '{query_cleaned[:100]}{'...' if len(query_cleaned) > 100 else ''}' "
                   f"(length: {len(query_cleaned)}, top_k: {top_k}, threshold: {score_threshold})")
        
        # Check cache
        cache_key = self._get_cache_key(query_cleaned, top_k, score_threshold, filters)
        cached_result = self._get_from_cache(cache_key)
        
        if cached_result:
            self.stats["cache_hits"] += 1
            logger.debug("Returning cached search result")
            self._log_search_analytics(query_cleaned, cached_result, from_cache=True)
            return cached_result
        
        self.stats["cache_misses"] += 1
        
        try:
            # Generate query embedding
            embedding_start = time.time()
            query_embedding = await self.embedding_service.generate_embedding(
                query_cleaned,
                use_cache=True
            )
            embedding_time_ms = (time.time() - embedding_start) * 1000
            
            # Perform vector search
            search_start = time.time()
            search_results = await self.qdrant_service.search_vectors(
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                filter_conditions=filters
            )
            search_time_ms = (time.time() - search_start) * 1000
            
            # Convert and process results
            chunks = await self._convert_search_results(
                search_results, 
                include_metadata=include_metadata
            )
            
            # Handle empty results gracefully
            if not chunks:
                logger.info(f"No results found for query: '{query_cleaned[:50]}...'")
                self.stats["empty_results_count"] += 1
                
                # Create empty response with helpful information
                response = self._create_empty_search_response(
                    query=query_cleaned,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    embedding_time_ms=embedding_time_ms,
                    search_time_ms=search_time_ms,
                    filters=filters,
                    score_threshold=score_threshold
                )
            else:
                # Process and enhance results
                chunks = await self._enhance_search_results(chunks, query_cleaned)
                
                # Calculate total processing time
                processing_time_ms = (time.time() - start_time) * 1000
                
                # Create response
                response = SearchResponse(
                    query=query_cleaned,
                    chunks=chunks,
                    total_results=len(chunks),
                    processing_time_ms=processing_time_ms,
                    embedding_time_ms=embedding_time_ms,
                    search_time_ms=search_time_ms,
                    filters_applied=filters,
                    score_threshold_used=score_threshold if score_threshold > 0 else None
                )
            
            # Cache the result
            self._add_to_cache(cache_key, response)
            
            # Calculate final processing time
            final_processing_time_ms = (time.time() - start_time) * 1000
            
            # Update statistics and analytics
            self._update_stats_with_analytics(
                query_cleaned, response, final_processing_time_ms, 
                embedding_time_ms, search_time_ms, filters
            )
            
            # Log search completion
            self._log_search_analytics(query_cleaned, response, from_cache=False)
            
            return response
            
        except Exception as e:
            logger.error(f"Search failed for query '{query_cleaned[:50]}...': {e}")
            raise
    
    async def _convert_search_results(
        self, 
        search_results: List[SearchResult], 
        include_metadata: bool = True
    ) -> List[SearchResultChunk]:
        """Convert Qdrant search results to response format"""
        chunks = []
        
        for result in search_results:
            try:
                payload = result.payload
                
                # Extract required fields
                chunk = SearchResultChunk(
                    id=result.id,
                    doctype=payload.get("doctype", ""),
                    docname=payload.get("docname", ""),
                    field_name=payload.get("field_name", ""),
                    content=payload.get("content", ""),
                    score=result.score
                )
                
                # Add optional metadata if requested
                if include_metadata:
                    chunk.chunk_index = payload.get("chunk_index")
                    chunk.total_chunks = payload.get("total_chunks")
                    
                    # Handle timestamp
                    timestamp_str = payload.get("timestamp")
                    if timestamp_str:
                        try:
                            chunk.timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            pass
                    
                    chunk.source_url = payload.get("source_url")
                    chunk.content_length = payload.get("content_length")
                    chunk.word_count = payload.get("word_count")
                
                chunks.append(chunk)
                
            except Exception as e:
                logger.warning(f"Error converting search result {result.id}: {e}")
                continue
        
        return chunks
    
    def _create_empty_search_response(
        self,
        query: str,
        processing_time_ms: float,
        embedding_time_ms: float,
        search_time_ms: float,
        filters: Optional[Dict[str, Any]],
        score_threshold: Optional[float]
    ) -> SearchResponse:
        """Create a response for empty search results with helpful information"""
        return SearchResponse(
            query=query,
            chunks=[],
            total_results=0,
            processing_time_ms=processing_time_ms,
            embedding_time_ms=embedding_time_ms,
            search_time_ms=search_time_ms,
            filters_applied=filters,
            score_threshold_used=score_threshold if score_threshold and score_threshold > 0 else None
        )
    
    async def _enhance_search_results(
        self, 
        chunks: List[SearchResultChunk], 
        query: str
    ) -> List[SearchResultChunk]:
        """Enhance search results with additional processing"""
        # Sort by score (highest first)
        chunks.sort(key=lambda x: x.score, reverse=True)
        
        # Add query relevance indicators
        query_words = set(query.lower().split())
        
        for chunk in chunks:
            # Calculate simple word overlap for additional context
            content_words = set(chunk.content.lower().split())
            word_overlap = len(query_words.intersection(content_words))
            
            # Store as additional metadata (could be used for ranking)
            if hasattr(chunk, '__dict__'):
                chunk.__dict__['_query_word_overlap'] = word_overlap
        
        return chunks
    
    def _log_search_analytics(
        self, 
        query: str, 
        response: SearchResponse, 
        from_cache: bool = False
    ):
        """Log search analytics for monitoring and debugging"""
        cache_status = "CACHE_HIT" if from_cache else "CACHE_MISS"
        
        logger.info(
            f"SEARCH_ANALYTICS: {cache_status} | "
            f"Query: '{query[:50]}...' | "
            f"Results: {response.total_results} | "
            f"Time: {response.processing_time_ms:.1f}ms | "
            f"Filters: {response.filters_applied or 'None'}"
        )
        
        # Log detailed timing breakdown for non-cached results
        if not from_cache and hasattr(response, 'embedding_time_ms'):
            logger.debug(
                f"TIMING_BREAKDOWN: "
                f"Embedding: {response.embedding_time_ms:.1f}ms | "
                f"Search: {response.search_time_ms:.1f}ms | "
                f"Total: {response.processing_time_ms:.1f}ms"
            )
        
        # Log empty results with suggestions
        if response.total_results == 0:
            suggestions = self._generate_empty_result_suggestions(query, response.filters_applied)
            if suggestions:
                logger.info(f"EMPTY_RESULT_SUGGESTIONS: {suggestions}")
    
    def _generate_empty_result_suggestions(
        self, 
        query: str, 
        filters: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate suggestions for empty search results"""
        suggestions = []
        
        # Suggest removing filters if they exist
        if filters:
            suggestions.append("Try removing or relaxing filters")
        
        # Suggest shorter query if it's very long
        if len(query) > 100:
            suggestions.append("Try using a shorter, more specific query")
        
        # Suggest different keywords if query is very short
        if len(query.split()) < 2:
            suggestions.append("Try adding more descriptive keywords")
        
        # Suggest checking spelling
        suggestions.append("Check spelling and try synonyms")
        
        return suggestions
    
    def _update_stats_with_analytics(
        self,
        query: str,
        response: SearchResponse,
        processing_time_ms: float,
        embedding_time_ms: float,
        search_time_ms: float,
        filters: Optional[Dict[str, Any]]
    ):
        """Update statistics with enhanced analytics"""
        # Update basic stats
        self._update_stats(processing_time_ms, embedding_time_ms, search_time_ms)
        
        # Update query length statistics
        query_length = len(query)
        if self.stats["query_length_stats"]["min"] == 0 or query_length < self.stats["query_length_stats"]["min"]:
            self.stats["query_length_stats"]["min"] = query_length
        if query_length > self.stats["query_length_stats"]["max"]:
            self.stats["query_length_stats"]["max"] = query_length
        
        # Update average query length
        total_queries = self.stats["total_queries"]
        current_avg = self.stats["query_length_stats"]["avg"]
        self.stats["query_length_stats"]["avg"] = (
            (current_avg * (total_queries - 1) + query_length) / total_queries
        )
        
        # Update results per query average
        current_results_avg = self.stats["avg_results_per_query"]
        self.stats["avg_results_per_query"] = (
            (current_results_avg * (total_queries - 1) + response.total_results) / total_queries
        )
        
        # Track doctype popularity
        if response.chunks:
            for chunk in response.chunks:
                doctype = chunk.doctype
                if doctype:
                    self.stats["top_doctypes"][doctype] = self.stats["top_doctypes"].get(doctype, 0) + 1
        
        # Track filtered queries
        if filters:
            self.stats["filtered_results_count"] += 1
    
    def _update_stats(self, processing_time_ms: float, embedding_time_ms: float, search_time_ms: float):
        """Update service statistics"""
        self.stats["total_queries"] += 1
        
        # Update running averages
        total_queries = self.stats["total_queries"]
        
        self.stats["avg_processing_time_ms"] = (
            (self.stats["avg_processing_time_ms"] * (total_queries - 1) + processing_time_ms) / total_queries
        )
        
        self.stats["avg_embedding_time_ms"] = (
            (self.stats["avg_embedding_time_ms"] * (total_queries - 1) + embedding_time_ms) / total_queries
        )
        
        self.stats["avg_search_time_ms"] = (
            (self.stats["avg_search_time_ms"] * (total_queries - 1) + search_time_ms) / total_queries
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        try:
            # Get Qdrant collection info
            collection_info = await self.qdrant_service.get_collection_info()
            
            return {
                **self.stats,
                "cache_size": len(self.result_cache),
                "embedding_cache_size": self.embedding_service.get_cache_size(),
                "vector_db_points_count": collection_info.get("points_count", 0),
                "service_ready": self.is_ready(),
                "embedding_service_ready": self.embedding_service.is_ready(),
                "vector_db_ready": self.qdrant_service.is_ready()
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                **self.stats,
                "cache_size": len(self.result_cache),
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        try:
            health_info = {
                "status": "healthy",
                "timestamp": datetime.utcnow(),
                "embedding_service_ready": self.embedding_service.is_ready(),
                "vector_db_ready": self.qdrant_service.is_ready(),
                "cache_size": len(self.result_cache)
            }
            
            # Get vector DB info
            try:
                collection_info = await self.qdrant_service.get_collection_info()
                health_info["vector_db_points_count"] = collection_info.get("points_count", 0)
            except Exception as e:
                logger.warning(f"Could not get vector DB info: {e}")
                health_info["vector_db_points_count"] = None
            
            # Check if service is fully ready
            if not self.is_ready():
                health_info["status"] = "unhealthy"
                health_info["error"] = "Service dependencies not ready"
            
            return health_info
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow(),
                "error": str(e)
            }
    
    async def clear_cache(self) -> Dict[str, int]:
        """Clear all caches"""
        result_cache_size = len(self.result_cache)
        self.result_cache.clear()
        
        embedding_cache_size = await self.embedding_service.clear_cache()
        
        logger.info(f"Cleared caches: {result_cache_size} results, {embedding_cache_size} embeddings")
        
        return {
            "result_cache_cleared": result_cache_size,
            "embedding_cache_cleared": embedding_cache_size
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Query Service")
        
        # Clear caches
        self.result_cache.clear()
        
        # Cleanup dependencies
        if self.embedding_service:
            await self.embedding_service.cleanup()
        
        if self.qdrant_service:
            await self.qdrant_service.cleanup()
        
        self._ready = False