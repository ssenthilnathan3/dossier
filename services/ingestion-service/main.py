"""
Document Ingestion Service

FastAPI service that processes documents from Frappe and manages ingestion workflows.
"""

import os
import signal
import asyncio
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from database import init_db
from api.routes import router as api_router
from shared.monitoring.fastapi_middleware import setup_monitoring
from shared.monitoring.logger import get_logger
from shared.monitoring.metrics import timed, count_calls
from shared.monitoring.tracing import trace_operation

# Ensure shared is in sys.path for monitoring imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Set up structured logging
logger = get_logger("ingestion-service")

# Global shutdown event
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting ingestion service...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ingestion service...")
    shutdown_event.set()
    
    # Give time for ongoing operations to complete
    shutdown_timeout = int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
    try:
        await asyncio.wait_for(cleanup_resources(), timeout=shutdown_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Graceful shutdown timeout ({shutdown_timeout}s) exceeded")
    
    logger.info("Ingestion service shutdown complete")

async def cleanup_resources():
    """Clean up resources during shutdown"""
    try:
        # Close database connections
        from database import engine
        if engine:
            await engine.dispose()
            logger.info("Database connections closed")
        
        # Add any other cleanup tasks here
        # e.g., close Redis connections, cancel background tasks, etc.
        
    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")


app = FastAPI(
    title="Dossier Ingestion Service",
    description="Document ingestion and processing service for Dossier RAG system",
    version="1.0.0",
    lifespan=lifespan
)

# Set up comprehensive monitoring
app = setup_monitoring(app, "ingestion-service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ingestion"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Dossier Ingestion Service", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)