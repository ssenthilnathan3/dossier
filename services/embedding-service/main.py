"""
Embedding Service - Main FastAPI application
"""

import os
import signal
import asyncio
import logging
import time
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService, VectorPoint
from models.requests import (
    EmbeddingRequest, BatchEmbeddingRequest, VectorUpsertRequest, 
    BatchVectorUpsertRequest, VectorSearchRequest, VectorDeleteRequest
)
from models.responses import (
    EmbeddingResponse, BatchEmbeddingResponse, HealthResponse,
    VectorSearchResponse, VectorSearchResult, VectorUpsertResponse, 
    VectorDeleteResponse, QdrantHealthResponse
)

# Import monitoring components
from shared.monitoring.fastapi_middleware import setup_monitoring, get_request_context
from shared.monitoring.logger import get_logger
from shared.monitoring.metrics import timed, count_calls
from shared.monitoring.tracing import trace_operation

# Load environment variables
load_dotenv()

# Set up structured logging
logger = get_logger("embedding-service")

# Global service instances
embedding_service = None
qdrant_service = None


# Global shutdown event
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global embedding_service, qdrant_service
    
    # Startup
    logger.info("Starting Embedding Service...")
    try:
        # Initialize embedding service
        embedding_service = EmbeddingService()
        await embedding_service.initialize()
        logger.info("Embedding Service initialized successfully")
        
        # Initialize Qdrant service
        qdrant_service = QdrantService()
        await qdrant_service.initialize()
        logger.info("Qdrant Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")
    shutdown_event.set()
    
    # Give time for ongoing operations to complete
    shutdown_timeout = int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
    try:
        await asyncio.wait_for(cleanup_resources(), timeout=shutdown_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Graceful shutdown timeout ({shutdown_timeout}s) exceeded")
    
    logger.info("Embedding service shutdown complete")

async def cleanup_resources():
    """Clean up resources during shutdown"""
    global embedding_service, qdrant_service
    try:
        if embedding_service:
            await embedding_service.cleanup()
            logger.info("Embedding service cleaned up")
        
        if qdrant_service:
            await qdrant_service.cleanup()
            logger.info("Qdrant service cleaned up")
            
    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")


# Create FastAPI app
app = FastAPI(
    title="Dossier Embedding Service",
    description="BGE-small embedding generation service for Dossier RAG system",
    version="1.0.0",
    lifespan=lifespan
)

# Set up comprehensive monitoring
app = setup_monitoring(app, "embedding-service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not embedding_service or not embedding_service.is_ready():
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Get Qdrant health
    qdrant_health = await qdrant_service.health_check() if qdrant_service else {
        "status": "unhealthy",
        "error": "Qdrant service not initialized"
    }
    
    # Convert to response model
    if qdrant_health["status"] == "healthy":
        qdrant_response = QdrantHealthResponse(
            status=qdrant_health["status"],
            collection=qdrant_health["collection"],
            points_count=qdrant_health["points_count"],
            response_time_ms=qdrant_health["response_time_ms"]
        )
    else:
        # Handle unhealthy case
        qdrant_response = QdrantHealthResponse(
            status=qdrant_health["status"],
            collection="unknown",
            points_count=0,
            response_time_ms=0.0
        )
    
    return HealthResponse(
        status="healthy",
        model_loaded=embedding_service.is_model_loaded(),
        cache_size=embedding_service.get_cache_size(),
        qdrant=qdrant_response
    )


@app.post("/embed", response_model=EmbeddingResponse)
async def generate_embedding(request: EmbeddingRequest):
    """Generate embedding for a single text"""
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        embedding = await embedding_service.generate_embedding(
            text=request.text,
            use_cache=request.use_cache
        )
        
        return EmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding),
            model="bge-small-en-v1.5"
        )
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/batch", response_model=BatchEmbeddingResponse)
async def generate_batch_embeddings(request: BatchEmbeddingRequest):
    """Generate embeddings for multiple texts"""
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        embeddings = await embedding_service.generate_batch_embeddings(
            texts=request.texts,
            batch_size=request.batch_size,
            use_cache=request.use_cache
        )
        
        return BatchEmbeddingResponse(
            embeddings=embeddings,
            count=len(embeddings),
            dimension=len(embeddings[0]) if embeddings else 0,
            model="bge-small-en-v1.5"
        )
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache")
async def clear_cache():
    """Clear the embedding cache"""
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        cleared_count = await embedding_service.clear_cache()
        return {"message": f"Cache cleared, removed {cleared_count} entries"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectors/upsert", response_model=VectorUpsertResponse)
async def upsert_vector(request: VectorUpsertRequest):
    """Upsert a single vector to Qdrant"""
    if not qdrant_service:
        raise HTTPException(status_code=503, detail="Qdrant service not initialized")
    
    try:
        start_time = time.time()
        
        vector_point = VectorPoint(
            id=request.id,
            vector=request.vector,
            payload=request.payload
        )
        
        success = await qdrant_service.upsert_vectors([vector_point])
        operation_time = (time.time() - start_time) * 1000
        
        return VectorUpsertResponse(
            success=success,
            upserted_count=1,
            operation_time_ms=round(operation_time, 2)
        )
    except Exception as e:
        logger.error(f"Error upserting vector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectors/upsert/batch", response_model=VectorUpsertResponse)
async def upsert_vectors_batch(request: BatchVectorUpsertRequest):
    """Upsert multiple vectors to Qdrant"""
    if not qdrant_service:
        raise HTTPException(status_code=503, detail="Qdrant service not initialized")
    
    try:
        start_time = time.time()
        
        vector_points = [
            VectorPoint(
                id=vector.id,
                vector=vector.vector,
                payload=vector.payload
            )
            for vector in request.vectors
        ]
        
        success = await qdrant_service.upsert_vectors(
            vector_points, 
            batch_size=request.batch_size
        )
        operation_time = (time.time() - start_time) * 1000
        
        return VectorUpsertResponse(
            success=success,
            upserted_count=len(vector_points),
            operation_time_ms=round(operation_time, 2)
        )
    except Exception as e:
        logger.error(f"Error upserting vectors batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectors/search", response_model=VectorSearchResponse)
async def search_vectors(request: VectorSearchRequest):
    """Search for similar vectors in Qdrant"""
    if not qdrant_service:
        raise HTTPException(status_code=503, detail="Qdrant service not initialized")
    
    try:
        start_time = time.time()
        
        search_results = await qdrant_service.search_vectors(
            query_vector=request.query_vector,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filter_conditions=request.filter_conditions
        )
        
        query_time = (time.time() - start_time) * 1000
        
        results = [
            VectorSearchResult(
                id=result.id,
                score=result.score,
                payload=result.payload
            )
            for result in search_results
        ]
        
        return VectorSearchResponse(
            results=results,
            count=len(results),
            query_time_ms=round(query_time, 2)
        )
    except Exception as e:
        logger.error(f"Error searching vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/vectors", response_model=VectorDeleteResponse)
async def delete_vectors(request: VectorDeleteRequest):
    """Delete vectors from Qdrant"""
    if not qdrant_service:
        raise HTTPException(status_code=503, detail="Qdrant service not initialized")
    
    try:
        start_time = time.time()
        
        success = await qdrant_service.delete_vectors(
            vector_ids=request.vector_ids,
            filter_conditions=request.filter_conditions
        )
        
        operation_time = (time.time() - start_time) * 1000
        
        # For simplicity, we'll return success without exact count
        # In a production system, you might want to get the actual count
        deleted_count = len(request.vector_ids) if request.vector_ids else 0
        
        return VectorDeleteResponse(
            success=success,
            deleted_count=deleted_count,
            operation_time_ms=round(operation_time, 2)
        )
    except Exception as e:
        logger.error(f"Error deleting vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vectors/collection/info")
async def get_collection_info():
    """Get Qdrant collection information"""
    if not qdrant_service:
        raise HTTPException(status_code=503, detail="Qdrant service not initialized")
    
    try:
        collection_info = await qdrant_service.get_collection_info()
        return collection_info
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8003))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development"
    )