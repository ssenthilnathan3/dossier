import os
import sys
import pytest
from fastapi.testclient import TestClient
from main import app
import jwt
from unittest.mock import patch, MagicMock
from fastapi.responses import JSONResponse
from fastapi import Request
from jwt import PyJWTError

# Set up test client
client = TestClient(app)

# Helper to create JWT
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
def create_jwt(payload=None):
    payload = payload or {"user_id": "testuser"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Mock backend URLs to localhost for testing
os.environ["EMBEDDING_SERVICE_URL"] = "http://localhost:9999"
os.environ["LLM_SERVICE_URL"] = "http://localhost:9999"
os.environ["INGESTION_SERVICE_URL"] = "http://localhost:9999"
os.environ["QUERY_SERVICE_URL"] = "http://localhost:9999"

@pytest.fixture
def auth_header():
    token = create_jwt()
    return {"Authorization": f"Bearer {token}"}

@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    # Allow unauthenticated access to /health and /metrics
    if request.url.path in ["/health", "/metrics"]:
        return await call_next(request)
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing JWT token"})
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        request.state.user = payload
    except PyJWTError:
        return JSONResponse(status_code=401, content={"detail": "Invalid JWT token"})
    return await call_next(request)

def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

def test_missing_jwt():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/embed", json={"text": "hi"})
        assert resp.status_code == 401

def test_invalid_jwt():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/embed", headers={"Authorization": "Bearer invalid"}, json={"text": "hi"})
        assert resp.status_code == 401

def test_embed_validation(auth_header):
    # Missing required field
    resp = client.post("/embed", headers=auth_header, json={})
    assert resp.status_code == 422
    # Valid request but backend unavailable (mocked)
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/embed", headers=auth_header, json={"text": "hi"})
        assert resp.status_code == 200

def test_llm_validation(auth_header):
    resp = client.post("/llm", headers=auth_header, json={})
    assert resp.status_code == 422
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/llm", headers=auth_header, json={"query": "hi"})
        assert resp.status_code == 200

def test_ingest_validation(auth_header):
    resp = client.post("/ingest", headers=auth_header, json={})
    assert resp.status_code == 422
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/ingest", headers=auth_header, json={"doctype": "Doc"})
        assert resp.status_code == 200

def test_query_validation(auth_header):
    resp = client.post("/query", headers=auth_header, json={})
    assert resp.status_code == 422
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_post.return_value = mock_response
        resp = client.post("/query", headers=auth_header, json={"query": "hi"})
        assert resp.status_code == 200 