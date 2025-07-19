"""
Query Service - Handles semantic search and retrieval operations
"""

import os
import signal
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys

# Ensure shared is in sys.path for monitoring imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

from services.query_service import QueryService
from models.requests import SearchRequest
from models.responses import SearchResponse, HealthResponse
from shared.monitoring.fastapi_middleware import setup_monitoring, get_request_context
from shared.monitoring.logger import get_logger
from shared.monitoring.metrics import timed, count_calls
from shared.monitoring.tracing import trace_operation

# Configure logging
logger = get_logger("query-service")

# Global service instance
query_service: QueryService = None


# Global shutdown event
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global query_service
    
    # Startup
    logger.info("Starting Query Service")
    query_service = QueryService()
    await query_service.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Query Service")
    shutdown_event.set()
    
    # Give time for ongoing operations to complete
    shutdown_timeout = int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
    try:
        await asyncio.wait_for(cleanup_resources(), timeout=shutdown_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Graceful shutdown timeout ({shutdown_timeout}s) exceeded")
    
    logger.info("Query service shutdown complete")

async def cleanup_resources():
    """Clean up resources during shutdown"""
    global query_service
    try:
        if query_service:
            await query_service.cleanup()
            logger.info("Query service cleaned up")
            
    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")


# Create FastAPI app
app = FastAPI(
    title="Dossier Query Service",
    description="Semantic search and retrieval service for RAG system",
    version="1.0.0",
    lifespan=lifespan
)

# Set up comprehensive monitoring
app = setup_monitoring(app, "query-service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_query_service() -> QueryService:
    """Dependency to get query service instance"""
    if not query_service or not query_service.is_ready():
        raise HTTPException(status_code=503, detail="Query service not ready")
    return query_service


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        if not query_service:
            return HealthResponse(
                status="unhealthy",
                error="Service not initialized"
            )
        
        health_info = await query_service.health_check()
        return HealthResponse(**health_info)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            error=str(e)
        )


@app.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """Perform semantic search"""
    try:
        logger.info(f"Processing search query: {request.query[:100]}...")
        
        result = await service.search(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            filters=request.filters,
            include_metadata=request.include_metadata
        )
        
        logger.info(f"Search completed, found {len(result.chunks)} results")
        return result
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats(service: QueryService = Depends(get_query_service)):
    """Get service statistics"""
    try:
        return await service.get_stats()
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development"
    )