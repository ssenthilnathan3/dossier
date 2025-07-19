"""
LLM Service - FastAPI application for LLM-based question answering using Ollama
"""

import os
import signal
import asyncio
import time
from typing import List, Optional
from contextlib import asynccontextmanager
import sys

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import ollama
from dotenv import load_dotenv
import json

from services.llm_service import LLMService
from models.requests import LLMRequest, ChatRequest, StreamingRequest, StreamingChatRequest
from models.responses import LLMResponse, ChatResponse, HealthResponse
from shared.monitoring.fastapi_middleware import setup_monitoring
from shared.monitoring.logger import get_logger
from shared.monitoring.metrics import timed, count_calls
from shared.monitoring.tracing import trace_operation

# Load environment variables
load_dotenv()

# Global shutdown event
shutdown_event = asyncio.Event()

# Ensure shared is in sys.path for monitoring imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Replace print statements with logger
logger = get_logger("llm-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting LLM Service...")
    
    # Initialize LLM service
    llm_service = LLMService()
    app.state.llm_service = llm_service
    
    # Test Ollama connection
    try:
        await llm_service.health_check()
        logger.info("✓ Ollama connection established")
    except Exception as e:
        logger.warning(f"⚠ Warning: Ollama connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down LLM Service...")
    shutdown_event.set()
    
    # Give time for ongoing operations to complete
    shutdown_timeout = int(os.getenv('GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
    try:
        await asyncio.wait_for(cleanup_resources(), timeout=shutdown_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Graceful shutdown timeout ({shutdown_timeout}s) exceeded")
    
    logger.info("LLM service shutdown complete")

async def cleanup_resources():
    """Clean up resources during shutdown"""
    try:
        # Add any cleanup tasks here
        # e.g., close connections, cancel background tasks, etc.
        logger.info("LLM service resources cleaned up")
            
    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")


# Create FastAPI app
app = FastAPI(
    title="Dossier LLM Service",
    description="LLM-based question answering service using Ollama",
    version="1.0.0",
    lifespan=lifespan
)

# Set up comprehensive monitoring
app = setup_monitoring(app, "llm-service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_llm_service() -> LLMService:
    """Dependency to get LLM service instance"""
    return app.state.llm_service


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        llm_service = get_llm_service()
        await llm_service.health_check()
        return HealthResponse(status="healthy", message="LLM service is running")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/generate", response_model=LLMResponse)
async def generate_response(
    request: LLMRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Generate a response using the LLM"""
    try:
        start_time = time.time()
        
        response = await llm_service.generate_response(
            query=request.query,
            context_chunks=request.context_chunks,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        processing_time = time.time() - start_time
        
        return LLMResponse(
            answer=response.answer,
            sources=response.sources,
            model_used=response.model_used,
            processing_time=processing_time,
            token_count=response.token_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Chat completion endpoint for conversational interactions"""
    try:
        start_time = time.time()
        
        response = await llm_service.chat_completion(
            messages=request.messages,
            context_chunks=request.context_chunks,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        processing_time = time.time() - start_time
        
        return ChatResponse(
            message=response.message,
            sources=response.sources,
            model_used=response.model_used,
            processing_time=processing_time,
            token_count=response.token_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete chat: {str(e)}")


@app.post("/generate/stream")
async def generate_streaming_response(
    request: StreamingRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Generate a streaming response using the LLM"""
    async def stream_generator():
        try:
            async for chunk in llm_service.generate_streaming_with_fallback(
                query=request.query,
                context_chunks=request.context_chunks,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                # Format as Server-Sent Events
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # End stream on completion or error
                if chunk.get('type') in ['complete', 'error']:
                    break
                    
        except Exception as e:
            error_chunk = {
                'type': 'error',
                'error': f"Streaming failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@app.post("/chat/stream")
async def chat_streaming_completion(
    request: StreamingChatRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Streaming chat completion endpoint"""
    async def stream_generator():
        try:
            async for chunk in llm_service.chat_streaming_completion(
                messages=request.messages,
                context_chunks=request.context_chunks,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                # Format as Server-Sent Events
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # End stream on completion or error
                if chunk.get('type') in ['complete', 'error']:
                    break
                    
        except Exception as e:
            error_chunk = {
                'type': 'error',
                'error': f"Streaming failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@app.get("/models")
async def list_models(llm_service: LLMService = Depends(get_llm_service)):
    """List available Ollama models"""
    try:
        models = await llm_service.list_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)