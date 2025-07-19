"""
Deployment validation tests for Docker containers and orchestration
"""

import pytest
import asyncio
import aiohttp
import docker
import time
import os
from typing import Dict, List
import subprocess
import json


class DockerDeploymentTester:
    """Test Docker deployment and orchestration"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.compose_file = "docker-compose.prod.yml"
        self.services = [
            "redis", "postgres", "qdrant", "webhook-handler",
            "ingestion-service", "embedding-service", "query-service",
            "llm-service", "frontend", "ollama"
        ]
        self.service_ports = {
            "redis": 6379,
            "postgres": 5432,
            "qdrant": 6333,
            "webhook-handler": 3001,
            "ingestion-service": 8001,
            "embedding-service": 8002,
            "query-service": 8003,
            "llm-service": 8004,
            "frontend": 3000,
            "ollama": 11434
        }
    
    async def test_docker_images_build(self):
        """Test that all Docker images can be built successfully"""
        print("Testing Docker image builds...")
        
        # Build all images
        result = subprocess.run([
            "docker-compose", "-f", self.compose_file, "build"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
        print("✓ All Docker images built successfully")
    
    async def test_services_start(self):
        """Test that all services start successfully"""
        print("Testing service startup...")
        
        # Start services
        result = subprocess.run([
            "docker-compose", "-f", self.compose_file, "up", "-d"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Service startup failed: {result.stderr}"
        
        # Wait for services to be ready
        await asyncio.sleep(30)
        print("✓ All services started")
    
    async def test_health_endpoints(self):
        """Test health endpoints for all services"""
        print("Testing health endpoints...")
        
        health_endpoints = {
            "webhook-handler": "http://localhost:3001/health",
            "ingestion-service": "http://localhost:8001/health",
            "embedding-service": "http://localhost:8002/health",
            "query-service": "http://localhost:8003/health",
            "llm-service": "http://localhost:8004/health",
            "frontend": "http://localhost:3000/health"
        }
        
        async with aiohttp.ClientSession() as session:
            for service, url in health_endpoints.items():
                try:
                    async with session.get(url, timeout=10) as response:
                        assert response.status == 200, f"{service} health check failed"
                        data = await response.json()
                        assert data.get("status") in ["healthy", "ok"], f"{service} reports unhealthy status"
                        print(f"✓ {service} health check passed")
                except Exception as e:
                    pytest.fail(f"{service} health check failed: {e}")
    
    async def test_container_resource_limits(self):
        """Test that containers respect resource limits"""
        print("Testing container resource limits...")
        
        containers = self.client.containers.list(filters={"label": "com.docker.compose.project=dossier"})
        
        for container in containers:
            stats = container.stats(stream=False)
            
            # Check memory usage
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100
            
            # Memory usage should be reasonable (less than 90% of limit)
            assert memory_percent < 90, f"Container {container.name} using {memory_percent:.1f}% memory"
            
            print(f"✓ {container.name} memory usage: {memory_percent:.1f}%")
    
    async def test_service_dependencies(self):
        """Test that service dependencies are working correctly"""
        print("Testing service dependencies...")
        
        # Test database connectivity
        await self._test_postgres_connection()
        await self._test_redis_connection()
        await self._test_qdrant_connection()
        
        print("✓ All service dependencies working")
    
    async def _test_postgres_connection(self):
        """Test PostgreSQL connection"""
        import asyncpg
        
        try:
            conn = await asyncpg.connect(
                host="localhost",
                port=5432,
                user="dossier",
                password=os.getenv("POSTGRES_PASSWORD", "dossier123"),
                database="dossier"
            )
            await conn.execute("SELECT 1")
            await conn.close()
            print("✓ PostgreSQL connection successful")
        except Exception as e:
            pytest.fail(f"PostgreSQL connection failed: {e}")
    
    async def _test_redis_connection(self):
        """Test Redis connection"""
        import redis.asyncio as redis
        
        try:
            r = redis.Redis(host="localhost", port=6379, decode_responses=True)
            await r.ping()
            await r.close()
            print("✓ Redis connection successful")
        except Exception as e:
            pytest.fail(f"Redis connection failed: {e}")
    
    async def _test_qdrant_connection(self):
        """Test Qdrant connection"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://localhost:6333/health") as response:
                    assert response.status == 200
                    print("✓ Qdrant connection successful")
            except Exception as e:
                pytest.fail(f"Qdrant connection failed: {e}")
    
    async def test_graceful_shutdown(self):
        """Test graceful shutdown of services"""
        print("Testing graceful shutdown...")
        
        # Send SIGTERM to services and check they shut down gracefully
        containers = self.client.containers.list(filters={"label": "com.docker.compose.project=dossier"})
        
        for container in containers:
            if container.name.endswith(("webhook-handler", "ingestion-service", "embedding-service", "query-service", "llm-service")):
                print(f"Testing graceful shutdown for {container.name}")
                
                # Send SIGTERM
                container.kill(signal="SIGTERM")
                
                # Wait for graceful shutdown (max 35 seconds)
                start_time = time.time()
                while container.status == "running" and (time.time() - start_time) < 35:
                    container.reload()
                    await asyncio.sleep(1)
                
                # Container should have stopped gracefully
                container.reload()
                assert container.status != "running", f"{container.name} did not shut down gracefully"
                print(f"✓ {container.name} shut down gracefully")
    
    async def test_service_restart_resilience(self):
        """Test that services can restart and recover properly"""
        print("Testing service restart resilience...")
        
        # Restart each service and verify it comes back healthy
        for service in ["webhook-handler", "ingestion-service", "embedding-service", "query-service"]:
            print(f"Testing restart resilience for {service}")
            
            # Restart service
            result = subprocess.run([
                "docker-compose", "-f", self.compose_file, "restart", service
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"Failed to restart {service}: {result.stderr}"
            
            # Wait for service to be ready
            await asyncio.sleep(10)
            
            # Check health endpoint
            port = self.service_ports[service]
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(f"http://localhost:{port}/health", timeout=10) as response:
                        assert response.status == 200, f"{service} not healthy after restart"
                        print(f"✓ {service} recovered successfully after restart")
                except Exception as e:
                    pytest.fail(f"{service} failed to recover after restart: {e}")
    
    async def test_volume_persistence(self):
        """Test that data persists across container restarts"""
        print("Testing volume persistence...")
        
        # Test Redis persistence
        import redis.asyncio as redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        test_key = "deployment_test_key"
        test_value = "deployment_test_value"
        
        await r.set(test_key, test_value)
        
        # Restart Redis
        subprocess.run([
            "docker-compose", "-f", self.compose_file, "restart", "redis"
        ], capture_output=True, text=True)
        
        await asyncio.sleep(5)
        
        # Check if data persisted
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        persisted_value = await r.get(test_key)
        assert persisted_value == test_value, "Redis data did not persist"
        await r.delete(test_key)
        await r.close()
        
        print("✓ Volume persistence working correctly")
    
    async def cleanup(self):
        """Clean up test environment"""
        print("Cleaning up test environment...")
        
        # Stop all services
        subprocess.run([
            "docker-compose", "-f", self.compose_file, "down", "-v"
        ], capture_output=True, text=True)
        
        print("✓ Test environment cleaned up")


@pytest.fixture
async def deployment_tester():
    """Fixture to provide deployment tester"""
    tester = DockerDeploymentTester()
    yield tester
    await tester.cleanup()


@pytest.mark.asyncio
async def test_full_deployment_validation(deployment_tester):
    """Run full deployment validation test suite"""
    print("Starting full deployment validation...")
    
    # Run all tests in sequence
    await deployment_tester.test_docker_images_build()
    await deployment_tester.test_services_start()
    await deployment_tester.test_health_endpoints()
    await deployment_tester.test_container_resource_limits()
    await deployment_tester.test_service_dependencies()
    await deployment_tester.test_volume_persistence()
    await deployment_tester.test_service_restart_resilience()
    await deployment_tester.test_graceful_shutdown()
    
    print("✓ All deployment validation tests passed!")


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_full_deployment_validation(DockerDeploymentTester()))