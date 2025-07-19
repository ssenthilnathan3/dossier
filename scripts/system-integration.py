#!/usr/bin/env python3
"""
System Integration Script for Dossier RAG System

This script orchestrates the complete system integration, ensuring all services
communicate correctly and the end-to-end workflow functions properly.
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

import httpx
import asyncpg
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('system-integration.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Service configuration"""
    name: str
    url: str
    health_endpoint: str
    required: bool = True


@dataclass
class IntegrationTest:
    """Integration test definition"""
    name: str
    description: str
    test_func: callable
    required: bool = True


class SystemIntegrator:
    """System integration orchestrator"""

    def __init__(self):
        self.services = self._load_service_configs()
        self.test_results = []
        self.session = None
        self.db_pool = None
        self.redis_client = None
        self.qdrant_client = None

    def _load_service_configs(self) -> Dict[str, ServiceConfig]:
        """Load service configurations"""
        return {
            'webhook_handler': ServiceConfig(
                name='Webhook Handler',
                url=os.getenv('WEBHOOK_URL', 'http://localhost:3001'),
                health_endpoint='/health'
            ),
            'ingestion_service': ServiceConfig(
                name='Ingestion Service',
                url=os.getenv('INGESTION_URL', 'http://localhost:8001'),
                health_endpoint='/health'
            ),
            'embedding_service': ServiceConfig(
                name='Embedding Service',
                url=os.getenv('EMBEDDING_URL', 'http://localhost:8002'),
                health_endpoint='/health'
            ),
            'query_service': ServiceConfig(
                name='Query Service',
                url=os.getenv('QUERY_URL', 'http://localhost:8003'),
                health_endpoint='/health'
            ),
            'llm_service': ServiceConfig(
                name='LLM Service',
                url=os.getenv('LLM_URL', 'http://localhost:8004'),
                health_endpoint='/health'
            ),
            'api_gateway': ServiceConfig(
                name='API Gateway',
                url=os.getenv('API_GATEWAY_URL', 'http://localhost:8080'),
                health_endpoint='/health'
            ),
            'frontend': ServiceConfig(
                name='Frontend',
                url=os.getenv('FRONTEND_URL', 'http://localhost:3000'),
                health_endpoint='/',
                required=False
            )
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_connections()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup_connections()

    async def initialize_connections(self):
        """Initialize all service connections"""
        logger.info("Initializing service connections...")

        # HTTP client
        self.session = httpx.AsyncClient(timeout=30.0)

        # Database connection
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://dossier:dossier123@localhost:5432/dossier')
            self.db_pool = await asyncpg.create_pool(database_url)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.db_pool = None

        # Redis connection
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None

        # Qdrant connection
        try:
            qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
            self.qdrant_client = QdrantClient(url=qdrant_url)
            logger.info("Qdrant connection established")
        except Exception as e:
            logger.error(f"Qdrant connection failed: {e}")
            self.qdrant_client = None

    async def cleanup_connections(self):
        """Clean up all connections"""
        if self.session:
            await self.session.aclose()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            self.redis_client.close()

    async def check_service_health(self, service_config: ServiceConfig) -> bool:
        """Check if a service is healthy"""
        try:
            response = await self.session.get(
                f"{service_config.url}{service_config.health_endpoint}",
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {service_config.name}: {e}")
            return False

    async def wait_for_services(self, max_wait: int = 300) -> bool:
        """Wait for all required services to be healthy"""
        logger.info("Waiting for services to become healthy...")

        start_time = time.time()
        while time.time() - start_time < max_wait:
            all_healthy = True

            for service_key, service_config in self.services.items():
                if not service_config.required:
                    continue

                healthy = await self.check_service_health(service_config)
                if not healthy:
                    logger.warning(f"{service_config.name} is not healthy")
                    all_healthy = False
                    break

            if all_healthy:
                logger.info("All required services are healthy")
                return True

            await asyncio.sleep(5)

        logger.error("Timeout waiting for services to become healthy")
        return False

    async def setup_database_schema(self):
        """Set up database schema and initial data"""
        if not self.db_pool:
            logger.error("Database connection not available")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                # Create doctype_configs table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS doctype_configs (
                        id SERIAL PRIMARY KEY,
                        doctype VARCHAR(255) NOT NULL UNIQUE,
                        enabled BOOLEAN DEFAULT true,
                        fields JSONB DEFAULT '[]',
                        filters JSONB DEFAULT '{}',
                        chunk_size INTEGER DEFAULT 1000,
                        chunk_overlap INTEGER DEFAULT 200,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Insert default configurations
                await conn.execute("""
                    INSERT INTO doctype_configs (doctype, enabled, fields, filters, chunk_size, chunk_overlap)
                    VALUES
                        ('Article', true, '["title", "content", "description"]', '{"status": "Published"}', 1000, 200),
                        ('Guide', true, '["title", "content", "summary"]', '{"status": "Active"}', 1200, 250),
                        ('TestDoc', true, '["title", "content"]', '{}', 800, 150)
                    ON CONFLICT (doctype) DO NOTHING
                """)

                logger.info("Database schema setup completed")
                return True

        except Exception as e:
            logger.error(f"Database schema setup failed: {e}")
            return False

    async def setup_vector_collections(self):
        """Set up vector database collections"""
        if not self.qdrant_client:
            logger.error("Qdrant connection not available")
            return False

        try:
            # Create documents collection
            collection_name = "documents"

            # Check if collection exists
            try:
                self.qdrant_client.get_collection(collection_name)
                logger.info(f"Collection '{collection_name}' already exists")
                return True
            except:
                pass

            # Create collection
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 embedding size
                    distance=Distance.COSINE
                )
            )

            logger.info(f"Vector collection '{collection_name}' created")
            return True

        except Exception as e:
            logger.error(f"Vector collection setup failed: {e}")
            return False

    async def test_webhook_processing(self) -> bool:
        """Test webhook processing pipeline"""
        logger.info("Testing webhook processing pipeline...")

        try:
            # Create test document
            test_doc = {
                "doctype": "TestDoc",
                "docname": f"INT-{uuid.uuid4().hex[:8]}",
                "operation": "create",
                "doc": {
                    "doctype": "TestDoc",
                    "name": f"INT-{uuid.uuid4().hex[:8]}",
                    "title": "Integration Test Document",
                    "content": "This is a test document for integration testing of the webhook processing pipeline."
                }
            }

            # Send webhook
            import hmac
            import hashlib

            webhook_secret = os.getenv('WEBHOOK_SECRET', 'webhooksecret')
            payload_str = json.dumps(test_doc, sort_keys=True)
            signature = hmac.new(
                webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()

            headers = {
                'X-Frappe-Webhook-Signature': f'sha256={signature}',
                'Content-Type': 'application/json'
            }

            response = await self.session.post(
                f"{self.services['webhook_handler'].url}/webhooks/frappe",
                json=test_doc,
                headers=headers
            )

            if response.status_code not in (200, 202):
                logger.error(f"Webhook processing failed: {response.status_code}")
                return False

            logger.info("Webhook processing test completed successfully")
            return True

        except Exception as e:
            logger.error(f"Webhook processing test failed: {e}")
            return False

    async def test_document_ingestion(self) -> bool:
        """Test document ingestion via API"""
        logger.info("Testing document ingestion...")

        try:
            # Trigger manual ingestion
            payload = {
                "doctype": "TestDoc",
                "batchSize": 5,
                "forceUpdate": True,
                "filters": {}
            }

            response = await self.session.post(
                f"{self.services['ingestion_service'].url}/api/ingestion/manual",
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Document ingestion failed: {response.status_code}")
                return False

            result = response.json()
            logger.info(f"Document ingestion completed: {result}")
            return True

        except Exception as e:
            logger.error(f"Document ingestion test failed: {e}")
            return False

    async def test_embedding_service(self) -> bool:
        """Test embedding service"""
        logger.info("Testing embedding service...")

        try:
            payload = {
                "text": "This is a test sentence for embedding generation.",
                "use_cache": False
            }

            response = await self.session.post(
                f"{self.services['embedding_service'].url}/embed",
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Embedding service failed: {response.status_code}")
                return False

            result = response.json()
            if "embedding" not in result or len(result["embedding"]) == 0:
                logger.error("Invalid embedding response")
                return False

            logger.info("Embedding service test completed successfully")
            return True

        except Exception as e:
            logger.error(f"Embedding service test failed: {e}")
            return False

    async def test_query_service(self) -> bool:
        """Test query service"""
        logger.info("Testing query service...")

        try:
            payload = {
                "query": "test document integration",
                "top_k": 5,
                "include_metadata": True
            }

            response = await self.session.post(
                f"{self.services['query_service'].url}/api/search",
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Query service failed: {response.status_code}")
                return False

            result = response.json()
            if "results" not in result:
                logger.error("Invalid query response")
                return False

            logger.info(f"Query service test completed: {len(result['results'])} results")
            return True

        except Exception as e:
            logger.error(f"Query service test failed: {e}")
            return False

    async def test_llm_service(self) -> bool:
        """Test LLM service"""
        logger.info("Testing LLM service...")

        try:
            payload = {
                "query": "What is a test document?",
                "context_chunks": [
                    {
                        "content": "A test document is used for testing purposes.",
                        "metadata": {"source": "test"}
                    }
                ],
                "model": "llama2",
                "temperature": 0.7
            }

            response = await self.session.post(
                f"{self.services['llm_service'].url}/generate",
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"LLM service failed: {response.status_code}")
                return False

            result = response.json()
            if "answer" not in result or len(result["answer"]) == 0:
                logger.error("Invalid LLM response")
                return False

            logger.info("LLM service test completed successfully")
            return True

        except Exception as e:
            logger.error(f"LLM service test failed: {e}")
            return False

    async def test_api_gateway(self) -> bool:
        """Test API Gateway integration"""
        logger.info("Testing API Gateway...")

        try:
            # Generate JWT token for testing
            import jwt

            jwt_secret = os.getenv('JWT_SECRET', 'supersecret')
            payload = {
                "user_id": "integration_test",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
                "sub": "integration_test"
            }
            token = jwt.encode(payload, jwt_secret, algorithm="HS256")

            headers = {"Authorization": f"Bearer {token}"}

            # Test query endpoint
            query_payload = {
                "query": "integration test",
                "top_k": 3,
                "include_metadata": True
            }

            response = await self.session.post(
                f"{self.services['api_gateway'].url}/query",
                json=query_payload,
                headers=headers
            )

            if response.status_code != 200:
                logger.error(f"API Gateway query failed: {response.status_code}")
                return False

            logger.info("API Gateway test completed successfully")
            return True

        except Exception as e:
            logger.error(f"API Gateway test failed: {e}")
            return False

    async def test_end_to_end_workflow(self) -> bool:
        """Test complete end-to-end workflow"""
        logger.info("Testing end-to-end workflow...")

        try:
            # 1. Create unique test document
            test_id = uuid.uuid4().hex[:8]
            test_doc = {
                "doctype": "TestDoc",
                "docname": f"E2E-{test_id}",
                "operation": "create",
                "doc": {
                    "doctype": "TestDoc",
                    "name": f"E2E-{test_id}",
                    "title": "End-to-End Integration Test",
                    "content": f"This is an end-to-end integration test document with unique ID {test_id}."
                }
            }

            # 2. Send webhook
            import hmac
            import hashlib

            webhook_secret = os.getenv('WEBHOOK_SECRET', 'webhooksecret')
            payload_str = json.dumps(test_doc, sort_keys=True)
            signature = hmac.new(
                webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()

            headers = {
                'X-Frappe-Webhook-Signature': f'sha256={signature}',
                'Content-Type': 'application/json'
            }

            response = await self.session.post(
                f"{self.services['webhook_handler'].url}/webhooks/frappe",
                json=test_doc,
                headers=headers
            )

            if response.status_code not in (200, 202):
                logger.error(f"E2E: Webhook failed: {response.status_code}")
                return False

            # 3. Wait for processing
            await asyncio.sleep(10)

            # 4. Query for the document
            query_payload = {
                "query": f"end-to-end integration test {test_id}",
                "top_k": 5,
                "include_metadata": True
            }

            response = await self.session.post(
                f"{self.services['query_service'].url}/api/search",
                json=query_payload
            )

            if response.status_code != 200:
                logger.error(f"E2E: Query failed: {response.status_code}")
                return False

            result = response.json()
            if not result.get("results"):
                logger.error("E2E: No search results found")
                return False

            # 5. Generate LLM response
            llm_payload = {
                "query": f"What is the document {test_id} about?",
                "context_chunks": result["results"][:2],
                "model": "llama2",
                "temperature": 0.7
            }

            response = await self.session.post(
                f"{self.services['llm_service'].url}/generate",
                json=llm_payload
            )

            if response.status_code != 200:
                logger.error(f"E2E: LLM generation failed: {response.status_code}")
                return False

            llm_result = response.json()
            if not llm_result.get("answer"):
                logger.error("E2E: No LLM answer generated")
                return False

            logger.info("End-to-end workflow test completed successfully")
            return True

        except Exception as e:
            logger.error(f"End-to-end workflow test failed: {e}")
            return False

    async def run_integration_tests(self) -> Dict[str, bool]:
        """Run all integration tests"""
        logger.info("Starting integration tests...")

        tests = [
            IntegrationTest("Service Health", "Check all services are healthy", self.wait_for_services),
            IntegrationTest("Database Schema", "Setup database schema", self.setup_database_schema),
            IntegrationTest("Vector Collections", "Setup vector collections", self.setup_vector_collections),
            IntegrationTest("Webhook Processing", "Test webhook processing", self.test_webhook_processing),
            IntegrationTest("Document Ingestion", "Test document ingestion", self.test_document_ingestion),
            IntegrationTest("Embedding Service", "Test embedding service", self.test_embedding_service),
            IntegrationTest("Query Service", "Test query service", self.test_query_service),
            IntegrationTest("LLM Service", "Test LLM service", self.test_llm_service),
            IntegrationTest("API Gateway", "Test API Gateway", self.test_api_gateway),
            IntegrationTest("End-to-End Workflow", "Test complete workflow", self.test_end_to_end_workflow)
        ]

        results = {}

        for test in tests:
            logger.info(f"Running test: {test.name}")
            try:
                start_time = time.time()
                success = await test.test_func()
                duration = time.time() - start_time

                results[test.name] = {
                    "success": success,
                    "duration": duration,
                    "description": test.description
                }

                status = "PASSED" if success else "FAILED"
                logger.info(f"Test {test.name}: {status} ({duration:.2f}s)")

                if not success and test.required:
                    logger.error(f"Required test {test.name} failed, stopping integration")
                    break

            except Exception as e:
                logger.error(f"Test {test.name} failed with exception: {e}")
                results[test.name] = {
                    "success": False,
                    "duration": 0,
                    "description": test.description,
                    "error": str(e)
                }

        return results

    def generate_report(self, results: Dict[str, bool]) -> str:
        """Generate integration test report"""
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r["success"])
        failed_tests = total_tests - passed_tests

        report = f"""
========================================
DOSSIER SYSTEM INTEGRATION REPORT
========================================

Timestamp: {datetime.now().isoformat()}
Total Tests: {total_tests}
Passed: {passed_tests}
Failed: {failed_tests}
Success Rate: {(passed_tests/total_tests)*100:.1f}%

Test Details:
"""

        for test_name, result in results.items():
            status = "PASSED" if result["success"] else "FAILED"
            duration = result.get("duration", 0)
            description = result.get("description", "")

            report += f"""
- {test_name}: {status} ({duration:.2f}s)
  Description: {description}
"""

            if not result["success"] and "error" in result:
                report += f"  Error: {result['error']}\n"

        report += f"""
========================================
System Status: {"HEALTHY" if failed_tests == 0 else "UNHEALTHY"}
========================================
"""

        return report


async def main():
    """Main integration function"""
    logger.info("Starting Dossier System Integration...")

    async with SystemIntegrator() as integrator:
        # Run integration tests
        results = await integrator.run_integration_tests()

        # Generate report
        report = integrator.generate_report(results)

        # Save report
        with open("integration-report.txt", "w") as f:
            f.write(report)

        # Print report
        print(report)

        # Exit with appropriate code
        failed_tests = sum(1 for r in results.values() if not r["success"])
        if failed_tests > 0:
            logger.error(f"Integration failed with {failed_tests} failed tests")
            sys.exit(1)
        else:
            logger.info("Integration completed successfully")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
