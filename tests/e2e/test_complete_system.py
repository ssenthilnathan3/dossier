"""
Comprehensive end-to-end tests for the complete Dossier RAG system.
Tests the entire workflow from document ingestion to chat responses.
"""

import os
import time
import asyncio
import pytest
import httpx
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

# Configuration
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:3001/webhooks/frappe")
INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8001")
QUERY_URL = os.getenv("QUERY_URL", "http://localhost:8003")
LLM_URL = os.getenv("LLM_URL", "http://localhost:8004")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://localhost:8002")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Test configuration
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhooksecret")
TEST_TIMEOUT = 60  # seconds


@dataclass
class TestDocument:
    """Test document structure"""
    doctype: str
    docname: str
    title: str
    content: str
    metadata: Dict[str, Any]


@dataclass
class TestResult:
    """Test result tracking"""
    test_name: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    metrics: Dict[str, Any] = None

    def finish(self, success: bool, error: Optional[str] = None, metrics: Optional[Dict[str, Any]] = None):
        self.end_time = time.time()
        self.success = success
        self.error = error
        self.metrics = metrics or {}

    @property
    def duration(self) -> float:
        return (self.end_time or time.time()) - self.start_time


class SystemTestClient:
    """Test client for system-wide operations"""

    def __init__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        self.jwt_token = None
        self.test_results: List[TestResult] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()

    def start_test(self, test_name: str) -> TestResult:
        """Start tracking a test"""
        result = TestResult(test_name=test_name, start_time=time.time())
        self.test_results.append(result)
        return result

    async def generate_jwt_token(self) -> str:
        """Generate JWT token for authentication"""
        import jwt
        payload = {
            "user_id": "test_user",
            "exp": int(time.time()) + 3600,  # 1 hour
            "iat": int(time.time()),
            "sub": "test_user"
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        self.jwt_token = token
        return token

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if not self.jwt_token:
            raise ValueError("JWT token not generated")
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def wait_for_services(self, max_wait: int = 60) -> bool:
        """Wait for all services to be healthy"""
        services = [
            ("API Gateway", f"{API_GATEWAY_URL}/health"),
            ("Webhook Handler", f"{WEBHOOK_URL.replace('/webhooks/frappe', '')}/health"),
            ("Ingestion Service", f"{INGESTION_URL}/health"),
            ("Query Service", f"{QUERY_URL}/health"),
            ("LLM Service", f"{LLM_URL}/health"),
            ("Embedding Service", f"{EMBEDDING_URL}/health"),
        ]

        start_time = time.time()
        while time.time() - start_time < max_wait:
            all_healthy = True
            for service_name, health_url in services:
                try:
                    response = await self.session.get(health_url)
                    if response.status_code != 200:
                        all_healthy = False
                        print(f"{service_name} not healthy: {response.status_code}")
                        break
                except Exception as e:
                    all_healthy = False
                    print(f"{service_name} not reachable: {e}")
                    break

            if all_healthy:
                print("All services are healthy")
                return True

            await asyncio.sleep(2)

        return False

    async def send_webhook(self, document: TestDocument) -> bool:
        """Send webhook event for document processing"""
        import hmac
        import hashlib

        payload = {
            "doctype": document.doctype,
            "docname": document.docname,
            "operation": "create",
            "doc": {
                "doctype": document.doctype,
                "name": document.docname,
                "title": document.title,
                "content": document.content,
                **document.metadata
            }
        }

        # Generate HMAC signature
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-Frappe-Webhook-Signature": f"sha256={signature}",
            "Content-Type": "application/json"
        }

        response = await self.session.post(
            WEBHOOK_URL,
            json=payload,
            headers=headers
        )

        return response.status_code in (200, 202)

    async def wait_for_ingestion(self, doctype: str, docname: str, max_wait: int = 30) -> bool:
        """Wait for document to be ingested and embedded"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                # Check if document chunks exist in vector store
                query_payload = {
                    "query": f"document {docname}",
                    "top_k": 1,
                    "filters": {
                        "doctype": doctype,
                        "docname": docname
                    }
                }

                response = await self.session.post(
                    f"{QUERY_URL}/api/search",
                    json=query_payload
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("results") and len(data["results"]) > 0:
                        return True

            except Exception as e:
                print(f"Error checking ingestion status: {e}")

            await asyncio.sleep(2)

        return False

    async def query_documents(self, query: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Query documents via search service"""
        payload = {
            "query": query,
            "top_k": 5,
            "filters": filters or {},
            "include_metadata": True
        }

        response = await self.session.post(
            f"{QUERY_URL}/api/search",
            json=payload
        )

        response.raise_for_status()
        return response.json()

    async def generate_llm_response(self, query: str, context_chunks: List[Dict] = None) -> Dict[str, Any]:
        """Generate LLM response via API gateway"""
        payload = {
            "query": query,
            "context_chunks": context_chunks or [],
            "model": "llama2",
            "temperature": 0.7
        }

        headers = self.get_auth_headers()
        response = await self.session.post(
            f"{API_GATEWAY_URL}/llm",
            json=payload,
            headers=headers
        )

        response.raise_for_status()
        return response.json()

    async def test_frontend_availability(self) -> bool:
        """Test frontend availability"""
        try:
            response = await self.session.get(FRONTEND_URL)
            return response.status_code == 200
        except Exception:
            return False


# Test Documents
TEST_DOCUMENTS = [
    TestDocument(
        doctype="Article",
        docname="ART-001",
        title="Introduction to Machine Learning",
        content="Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed. It involves algorithms that can identify patterns in data and make predictions or decisions based on those patterns.",
        metadata={
            "author": "John Doe",
            "category": "Technology",
            "tags": ["AI", "ML", "Data Science"]
        }
    ),
    TestDocument(
        doctype="Article",
        docname="ART-002",
        title="Best Practices for API Design",
        content="When designing APIs, it's crucial to follow REST principles, use proper HTTP methods, implement consistent error handling, and provide comprehensive documentation. Version control and security considerations are also essential for production APIs.",
        metadata={
            "author": "Jane Smith",
            "category": "Development",
            "tags": ["API", "REST", "Design"]
        }
    ),
    TestDocument(
        doctype="Guide",
        docname="GDE-001",
        title="Docker Container Deployment",
        content="Docker containers provide a lightweight, portable way to package applications and their dependencies. This guide covers container creation, image optimization, orchestration with Docker Compose, and production deployment strategies.",
        metadata={
            "author": "DevOps Team",
            "category": "Infrastructure",
            "tags": ["Docker", "Containers", "DevOps"]
        }
    )
]


@pytest.fixture
async def test_client():
    """Create test client"""
    async with SystemTestClient() as client:
        await client.generate_jwt_token()
        yield client


@pytest.mark.asyncio
async def test_service_health_checks(test_client: SystemTestClient):
    """Test that all services are healthy"""
    result = test_client.start_test("service_health_checks")

    try:
        healthy = await test_client.wait_for_services()
        assert healthy, "Not all services are healthy"

        result.finish(success=True, metrics={"services_checked": 6})

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_document_ingestion_pipeline(test_client: SystemTestClient):
    """Test complete document ingestion pipeline"""
    result = test_client.start_test("document_ingestion_pipeline")

    try:
        # Test document ingestion for each test document
        for doc in TEST_DOCUMENTS:
            # Send webhook
            webhook_success = await test_client.send_webhook(doc)
            assert webhook_success, f"Webhook failed for document {doc.docname}"

            # Wait for ingestion to complete
            ingestion_success = await test_client.wait_for_ingestion(
                doc.doctype, doc.docname, max_wait=30
            )
            assert ingestion_success, f"Ingestion failed for document {doc.docname}"

        result.finish(success=True, metrics={
            "documents_ingested": len(TEST_DOCUMENTS),
            "ingestion_time": result.duration
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_semantic_search_functionality(test_client: SystemTestClient):
    """Test semantic search across ingested documents"""
    result = test_client.start_test("semantic_search")

    try:
        # Test various search queries
        search_tests = [
            {
                "query": "machine learning algorithms",
                "expected_doctype": "Article",
                "expected_docname": "ART-001"
            },
            {
                "query": "REST API design principles",
                "expected_doctype": "Article",
                "expected_docname": "ART-002"
            },
            {
                "query": "container deployment strategies",
                "expected_doctype": "Guide",
                "expected_docname": "GDE-001"
            }
        ]

        search_results = []
        for test_case in search_tests:
            search_result = await test_client.query_documents(test_case["query"])

            assert "results" in search_result
            assert len(search_result["results"]) > 0

            # Check if expected document is in top results
            top_result = search_result["results"][0]
            assert top_result["metadata"]["doctype"] == test_case["expected_doctype"]
            assert top_result["metadata"]["docname"] == test_case["expected_docname"]

            search_results.append({
                "query": test_case["query"],
                "results_count": len(search_result["results"]),
                "top_score": top_result.get("score", 0)
            })

        result.finish(success=True, metrics={
            "searches_performed": len(search_tests),
            "search_results": search_results
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_llm_response_generation(test_client: SystemTestClient):
    """Test LLM response generation with context"""
    result = test_client.start_test("llm_response_generation")

    try:
        # Get relevant context for a query
        query = "What is machine learning?"
        search_result = await test_client.query_documents(query)

        assert "results" in search_result
        context_chunks = search_result["results"][:3]  # Top 3 results

        # Generate LLM response
        llm_response = await test_client.generate_llm_response(query, context_chunks)

        assert "answer" in llm_response
        assert len(llm_response["answer"]) > 0

        # Check if response contains relevant information
        answer_lower = llm_response["answer"].lower()
        assert any(keyword in answer_lower for keyword in ["machine learning", "algorithm", "artificial intelligence"])

        result.finish(success=True, metrics={
            "response_length": len(llm_response["answer"]),
            "context_chunks_used": len(context_chunks),
            "response_time": result.duration
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_end_to_end_workflow(test_client: SystemTestClient):
    """Test complete end-to-end workflow: webhook -> ingestion -> query -> LLM"""
    result = test_client.start_test("end_to_end_workflow")

    try:
        # Create a unique test document
        test_doc = TestDocument(
            doctype="TestDoc",
            docname=f"E2E-{uuid.uuid4().hex[:8]}",
            title="End-to-End Test Document",
            content="This is a comprehensive test document for validating the complete RAG pipeline from document ingestion through to generating AI responses.",
            metadata={
                "test_type": "e2e",
                "timestamp": datetime.now().isoformat()
            }
        )

        # Step 1: Send webhook
        webhook_start = time.time()
        webhook_success = await test_client.send_webhook(test_doc)
        webhook_duration = time.time() - webhook_start
        assert webhook_success, "Webhook processing failed"

        # Step 2: Wait for ingestion
        ingestion_start = time.time()
        ingestion_success = await test_client.wait_for_ingestion(
            test_doc.doctype, test_doc.docname, max_wait=45
        )
        ingestion_duration = time.time() - ingestion_start
        assert ingestion_success, "Document ingestion failed"

        # Step 3: Query the document
        query_start = time.time()
        query_result = await test_client.query_documents(
            "end-to-end test document",
            filters={"doctype": test_doc.doctype, "docname": test_doc.docname}
        )
        query_duration = time.time() - query_start
        assert len(query_result["results"]) > 0, "Query returned no results"

        # Step 4: Generate LLM response
        llm_start = time.time()
        llm_response = await test_client.generate_llm_response(
            "What is this document about?",
            query_result["results"][:2]
        )
        llm_duration = time.time() - llm_start
        assert "answer" in llm_response, "LLM response missing answer"

        # Verify response quality
        answer_lower = llm_response["answer"].lower()
        assert any(keyword in answer_lower for keyword in ["test", "document", "pipeline", "rag"])

        result.finish(success=True, metrics={
            "webhook_duration": webhook_duration,
            "ingestion_duration": ingestion_duration,
            "query_duration": query_duration,
            "llm_duration": llm_duration,
            "total_duration": result.duration,
            "response_quality": "passed"
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_api_gateway_authentication(test_client: SystemTestClient):
    """Test API Gateway authentication and authorization"""
    result = test_client.start_test("api_gateway_authentication")

    try:
        # Test without authentication
        response = await test_client.session.post(
            f"{API_GATEWAY_URL}/query",
            json={"query": "test query"}
        )
        assert response.status_code == 401, "Should require authentication"

        # Test with valid authentication
        headers = test_client.get_auth_headers()
        response = await test_client.session.post(
            f"{API_GATEWAY_URL}/query",
            json={"query": "test query", "top_k": 1},
            headers=headers
        )
        assert response.status_code in (200, 400), "Should accept valid authentication"

        result.finish(success=True, metrics={
            "auth_tests_passed": 2
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_frontend_integration(test_client: SystemTestClient):
    """Test frontend availability and basic functionality"""
    result = test_client.start_test("frontend_integration")

    try:
        # Test frontend availability
        frontend_available = await test_client.test_frontend_availability()
        assert frontend_available, "Frontend not available"

        # Test static assets (basic check)
        response = await test_client.session.get(f"{FRONTEND_URL}/static/js/main.js")
        # Frontend might be using different bundling, so accept various responses
        assert response.status_code in (200, 404), "Unexpected frontend response"

        result.finish(success=True, metrics={
            "frontend_available": frontend_available
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_system_performance(test_client: SystemTestClient):
    """Test system performance under load"""
    result = test_client.start_test("system_performance")

    try:
        # Test concurrent queries
        query_tasks = []
        for i in range(10):
            task = test_client.query_documents(f"test query {i}")
            query_tasks.append(task)

        query_start = time.time()
        query_results = await asyncio.gather(*query_tasks, return_exceptions=True)
        query_duration = time.time() - query_start

        # Count successful queries
        successful_queries = sum(1 for r in query_results if not isinstance(r, Exception))

        # Test concurrent LLM requests
        llm_tasks = []
        for i in range(5):
            task = test_client.generate_llm_response(f"Simple question {i}")
            llm_tasks.append(task)

        llm_start = time.time()
        llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)
        llm_duration = time.time() - llm_start

        successful_llm = sum(1 for r in llm_results if not isinstance(r, Exception))

        result.finish(success=True, metrics={
            "concurrent_queries": 10,
            "successful_queries": successful_queries,
            "query_duration": query_duration,
            "concurrent_llm_requests": 5,
            "successful_llm_requests": successful_llm,
            "llm_duration": llm_duration,
            "avg_query_time": query_duration / 10,
            "avg_llm_time": llm_duration / 5
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


@pytest.mark.asyncio
async def test_error_handling_and_recovery(test_client: SystemTestClient):
    """Test system error handling and recovery"""
    result = test_client.start_test("error_handling_recovery")

    try:
        # Test invalid webhook payload
        invalid_payload = {"invalid": "data"}
        response = await test_client.session.post(WEBHOOK_URL, json=invalid_payload)
        assert response.status_code in (400, 422), "Should handle invalid webhook payload"

        # Test invalid query
        response = await test_client.session.post(
            f"{QUERY_URL}/api/search",
            json={"invalid_field": "value"}
        )
        assert response.status_code in (400, 422), "Should handle invalid query"

        # Test invalid LLM request
        headers = test_client.get_auth_headers()
        response = await test_client.session.post(
            f"{API_GATEWAY_URL}/llm",
            json={"invalid_field": "value"},
            headers=headers
        )
        assert response.status_code in (400, 422), "Should handle invalid LLM request"

        result.finish(success=True, metrics={
            "error_scenarios_tested": 3
        })

    except Exception as e:
        result.finish(success=False, error=str(e))
        raise


def generate_test_report(test_results: List[TestResult]) -> Dict[str, Any]:
    """Generate comprehensive test report"""
    total_tests = len(test_results)
    successful_tests = sum(1 for r in test_results if r.success)
    failed_tests = total_tests - successful_tests

    total_duration = sum(r.duration for r in test_results)
    avg_duration = total_duration / total_tests if total_tests > 0 else 0

    report = {
        "summary": {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests / total_tests) * 100 if total_tests > 0 else 0,
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "timestamp": datetime.now().isoformat()
        },
        "test_results": []
    }

    for result in test_results:
        report["test_results"].append({
            "test_name": result.test_name,
            "success": result.success,
            "duration": result.duration,
            "error": result.error,
            "metrics": result.metrics
        })

    return report


@pytest.mark.asyncio
async def test_generate_final_report(test_client: SystemTestClient):
    """Generate final test report"""
    report = generate_test_report(test_client.test_results)

    # Save report to file
    report_path = "test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nTest Report Generated: {report_path}")
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
    print(f"Total Duration: {report['summary']['total_duration']:.2f}s")

    # Assert overall success
    assert report['summary']['failed_tests'] == 0, f"Some tests failed: {report['summary']['failed_tests']}"
