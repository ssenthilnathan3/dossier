"""
Pytest configuration and fixtures for ingestion service tests
"""

import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from unittest.mock import Mock

# Add parent directories to path for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from database import Base, get_db
from models.database_models import DoctypeConfigModel
from api.routes import router as api_router

# Import JobStatus from shared models
try:
    from shared.models.base import JobStatus
except ImportError:
    # Fallback if shared module is not available
    from enum import Enum
    class JobStatus(str, Enum):
        QUEUED = "queued"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"


def create_test_app():
    """Create a test FastAPI app without database initialization"""
    app = FastAPI(
        title="Test Dossier Ingestion Service",
        description="Test version of document ingestion service",
        version="1.0.0-test"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router, prefix="/api")

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "ingestion-test"}

    @app.get("/")
    async def root():
        """Root endpoint"""
        return {"message": "Test Dossier Ingestion Service", "version": "1.0.0-test"}

    return app


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session"""
    # Create temporary database with proper SQLite threading configuration
    engine = create_engine(
        "sqlite:///:memory:", 
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        }
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    # Clean up
    test_app.dependency_overrides.clear()


@pytest.fixture
def sample_doctype_config(test_db):
    """Create a sample doctype configuration for testing"""
    config = DoctypeConfigModel(
        doctype="Item",
        enabled=True,
        fields=["item_name", "description", "item_group"],
        filters={"disabled": 0},
        chunk_size=1000,
        chunk_overlap=200
    )
    test_db.add(config)
    test_db.commit()
    test_db.refresh(config)
    return config


@pytest.fixture
def mock_frappe_client():
    """Mock Frappe client for testing"""
    client = Mock()
    client.test_connection.return_value = True
    client.get_documents.return_value = ([], 0)
    client.get_document.return_value = {}
    return client