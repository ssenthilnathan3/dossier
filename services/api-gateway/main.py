import os
import sys
from fastapi import FastAPI, Request, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import jwt
from jwt import PyJWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import httpx
from pydantic import BaseModel
from slowapi.extension import Limiter as SlowapiLimiter

# Ensure shared is in sys.path for monitoring imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
try:
    from shared.monitoring.fastapi_middleware import setup_monitoring
    from shared.monitoring.logger import get_logger
except ImportError:
    setup_monitoring = lambda app, name: app
    def get_logger(name):
        import logging
        logger = logging.getLogger(name)
        return logger

load_dotenv()

logger = get_logger("api-gateway")

app = FastAPI(
    title="Dossier API Gateway",
    description="API Gateway with JWT authentication, rate limiting, and proxying",
    version="1.0.0"
)

# Set up monitoring
app = setup_monitoring(app, "api-gateway")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

security = HTTPBearer()

async def verify_jwt(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if request.url.path in ["/health", "/metrics"]:
        return
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=401, detail="Missing JWT token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        request.state.user = payload
    except PyJWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid JWT token")

# Add JWT authentication dependency to all routes except /health and /metrics
from fastapi.routing import APIRoute
for route in app.routes:
    if isinstance(route, APIRoute) and route.path not in ["/health", "/metrics"]:
        route.dependant.dependencies.append(Depends(verify_jwt))

# Set up rate limiter (e.g., 100 requests per minute per IP)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"}
    )

# Decorator for rate limiting (skip /health and /metrics)
def rate_limit_exempt(request: Request):
    return request.url.path in ["/health", "/metrics"]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

# Backend service URLs (set these in your environment or docker-compose)
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8002")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8004")
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://ingestion-service:8001")
QUERY_SERVICE_URL = os.getenv("QUERY_SERVICE_URL", "http://query-service:8003")

# Example request validation for /embed
class EmbedRequest(BaseModel):
    text: str
    use_cache: bool = True

@app.post("/embed")
@limiter.limit("100/minute")
async def proxy_embed(request: Request, body: EmbedRequest = Body(...)):
    async with httpx.AsyncClient() as client:
        headers = dict(request.headers)
        response = await client.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json=body.dict(),
            headers=headers,
            timeout=30.0
        )
        return JSONResponse(status_code=response.status_code, content=response.json())

# Validation schemas for other endpoints
class LLMRequest(BaseModel):
    query: str
    context_chunks: list = []
    model: str = None
    temperature: float = None
    max_tokens: int = None

class IngestRequest(BaseModel):
    doctype: str
    batchSize: int = 1
    forceUpdate: bool = False
    filters: dict = {}

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    score_threshold: float = 0.0
    filters: dict = {}
    include_metadata: bool = True

@app.post("/llm")
@limiter.limit("100/minute")
async def proxy_llm(request: Request, body: LLMRequest = Body(...)):
    async with httpx.AsyncClient() as client:
        headers = dict(request.headers)
        try:
            response = await client.post(
                f"{LLM_SERVICE_URL}/generate",
                json=body.dict(),
                headers=headers,
                timeout=60.0
            )
            return JSONResponse(status_code=response.status_code, content=response.json())
        except httpx.RequestError as e:
            logger.error(f"LLM service error: {e}")
            raise HTTPException(status_code=502, detail="LLM service unavailable")

@app.post("/ingest")
@limiter.limit("100/minute")
async def proxy_ingest(request: Request, body: IngestRequest = Body(...)):
    async with httpx.AsyncClient() as client:
        headers = dict(request.headers)
        try:
            response = await client.post(
                f"{INGESTION_SERVICE_URL}/api/ingestion/manual",
                json=body.dict(),
                headers=headers,
                timeout=60.0
            )
            return JSONResponse(status_code=response.status_code, content=response.json())
        except httpx.RequestError as e:
            logger.error(f"Ingestion service error: {e}")
            raise HTTPException(status_code=502, detail="Ingestion service unavailable")

@app.post("/query")
@limiter.limit("100/minute")
async def proxy_query(request: Request, body: QueryRequest = Body(...)):
    async with httpx.AsyncClient() as client:
        headers = dict(request.headers)
        try:
            response = await client.post(
                f"{QUERY_SERVICE_URL}/api/search",
                json=body.dict(),
                headers=headers,
                timeout=60.0
            )
            return JSONResponse(status_code=response.status_code, content=response.json())
        except httpx.RequestError as e:
            logger.error(f"Query service error: {e}")
            raise HTTPException(status_code=502, detail="Query service unavailable")

# Placeholder for JWT authentication and proxy logic
# More endpoints and middleware will be added in the next steps 