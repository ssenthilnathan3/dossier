#!/usr/bin/env python3
"""
Deployment Validation Script for Dossier RAG System

This script validates the deployment of the Dossier RAG system by checking:
- Service availability and health
- Configuration validity
- Database connectivity
- External service dependencies
- Security settings
- Performance benchmarks
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid
import subprocess
import psutil

import httpx
import asyncpg
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('deployment-validation.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Validation result for a single check"""
    name: str
    status: str  # PASS, FAIL, WARN, SKIP
    message: str
    details: Optional[Dict[str, Any]] = None
    duration: float = 0.0
    critical: bool = True


@dataclass
class SystemRequirements:
    """System requirements definition"""
    min_cpu_cores: int = 4
    min_memory_gb: int = 8
    min_disk_gb: int = 50
    required_ports: List[int] = None
    required_env_vars: List[str] = None

    def __post_init__(self):
        if self.required_ports is None:
            self.required_ports = [3000, 3001, 5432, 6333, 6379, 8001, 8002, 8003, 8004, 8080, 11434]
        if self.required_env_vars is None:
            self.required_env_vars = [
                'DATABASE_URL', 'REDIS_URL', 'FRAPPE_URL', 'FRAPPE_API_KEY',
                'FRAPPE_API_SECRET', 'JWT_SECRET', 'WEBHOOK_SECRET'
            ]


class DeploymentValidator:
    """Comprehensive deployment validator"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.requirements = SystemRequirements()
        self.results: List[ValidationResult] = []
        self.session = None
        self.db_pool = None
        self.redis_client = None
        self.qdrant_client = None

    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or environment"""
        config = {}

        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)

        # Override with environment variables
        env_config = {
            'api_gateway_url': os.getenv('API_GATEWAY_URL', 'http://localhost:8080'),
            'webhook_url': os.getenv('WEBHOOK_URL', 'http://localhost:3001'),
            'ingestion_url': os.getenv('INGESTION_URL', 'http://localhost:8001'),
            'embedding_url': os.getenv('EMBEDDING_URL', 'http://localhost:8002'),
            'query_url': os.getenv('QUERY_URL', 'http://localhost:8003'),
            'llm_url': os.getenv('LLM_URL', 'http://localhost:8004'),
            'frontend_url': os.getenv('FRONTEND_URL', 'http://localhost:3000'),
            'database_url': os.getenv('DATABASE_URL', 'postgresql://dossier:dossier123@localhost:5432/dossier'),
            'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379'),
            'qdrant_url': os.getenv('QDRANT_URL', 'http://localhost:6333'),
            'ollama_url': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
            'frappe_url': os.getenv('FRAPPE_URL', ''),
            'jwt_secret': os.getenv('JWT_SECRET', ''),
            'webhook_secret': os.getenv('WEBHOOK_SECRET', ''),
            'environment': os.getenv('NODE_ENV', 'development')
        }

        config.update(env_config)
        return config

    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_connections()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup_connections()

    async def _initialize_connections(self):
        """Initialize service connections"""
        self.session = httpx.AsyncClient(timeout=30.0)

        # Initialize other connections (handled in specific validation methods)
        pass

    async def _cleanup_connections(self):
        """Clean up connections"""
        if self.session:
            await self.session.aclose()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.aclose()

    def _add_result(self, result: ValidationResult):
        """Add validation result"""
        self.results.append(result)

        # Log result
        if result.status == "PASS":
            logger.info(f"✓ {result.name}: {result.message}")
        elif result.status == "FAIL":
            logger.error(f"✗ {result.name}: {result.message}")
        elif result.status == "WARN":
            logger.warning(f"⚠ {result.name}: {result.message}")
        elif result.status == "SKIP":
            logger.info(f"- {result.name}: {result.message}")

    async def validate_system_requirements(self) -> ValidationResult:
        """Validate system requirements"""
        start_time = time.time()

        try:
            # Check CPU cores
            cpu_cores = psutil.cpu_count(logical=False)
            if cpu_cores < self.requirements.min_cpu_cores:
                return ValidationResult(
                    name="System Requirements",
                    status="WARN",
                    message=f"CPU cores: {cpu_cores} < {self.requirements.min_cpu_cores} (minimum)",
                    duration=time.time() - start_time,
                    critical=False
                )

            # Check memory
            memory_gb = psutil.virtual_memory().total / (1024**3)
            if memory_gb < self.requirements.min_memory_gb:
                return ValidationResult(
                    name="System Requirements",
                    status="WARN",
                    message=f"Memory: {memory_gb:.1f}GB < {self.requirements.min_memory_gb}GB (minimum)",
                    duration=time.time() - start_time,
                    critical=False
                )

            # Check disk space
            disk_gb = psutil.disk_usage('.').free / (1024**3)
            if disk_gb < self.requirements.min_disk_gb:
                return ValidationResult(
                    name="System Requirements",
                    status="WARN",
                    message=f"Disk space: {disk_gb:.1f}GB < {self.requirements.min_disk_gb}GB (minimum)",
                    duration=time.time() - start_time,
                    critical=False
                )

            return ValidationResult(
                name="System Requirements",
                status="PASS",
                message=f"CPU: {cpu_cores} cores, Memory: {memory_gb:.1f}GB, Disk: {disk_gb:.1f}GB",
                duration=time.time() - start_time,
                details={
                    "cpu_cores": cpu_cores,
                    "memory_gb": round(memory_gb, 1),
                    "disk_gb": round(disk_gb, 1)
                }
            )

        except Exception as e:
            return ValidationResult(
                name="System Requirements",
                status="FAIL",
                message=f"Failed to check system requirements: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_docker_environment(self) -> ValidationResult:
        """Validate Docker environment"""
        start_time = time.time()

        try:
            # Check Docker
            docker_result = subprocess.run(['docker', '--version'],
                                         capture_output=True, text=True)
            if docker_result.returncode != 0:
                return ValidationResult(
                    name="Docker Environment",
                    status="FAIL",
                    message="Docker not installed or not accessible",
                    duration=time.time() - start_time
                )

            # Check Docker Compose
            compose_result = subprocess.run(['docker-compose', '--version'],
                                          capture_output=True, text=True)
            if compose_result.returncode != 0:
                return ValidationResult(
                    name="Docker Environment",
                    status="FAIL",
                    message="Docker Compose not installed or not accessible",
                    duration=time.time() - start_time
                )

            # Check Docker daemon
            daemon_result = subprocess.run(['docker', 'info'],
                                         capture_output=True, text=True)
            if daemon_result.returncode != 0:
                return ValidationResult(
                    name="Docker Environment",
                    status="FAIL",
                    message="Docker daemon not running",
                    duration=time.time() - start_time
                )

            return ValidationResult(
                name="Docker Environment",
                status="PASS",
                message="Docker and Docker Compose are available",
                duration=time.time() - start_time,
                details={
                    "docker_version": docker_result.stdout.strip(),
                    "compose_version": compose_result.stdout.strip()
                }
            )

        except Exception as e:
            return ValidationResult(
                name="Docker Environment",
                status="FAIL",
                message=f"Docker environment check failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_configuration(self) -> ValidationResult:
        """Validate configuration completeness"""
        start_time = time.time()

        try:
            missing_vars = []
            empty_vars = []

            for var in self.requirements.required_env_vars:
                value = os.getenv(var)
                if value is None:
                    missing_vars.append(var)
                elif not value.strip():
                    empty_vars.append(var)

            if missing_vars:
                return ValidationResult(
                    name="Configuration",
                    status="FAIL",
                    message=f"Missing required environment variables: {', '.join(missing_vars)}",
                    duration=time.time() - start_time,
                    details={"missing_vars": missing_vars}
                )

            if empty_vars:
                return ValidationResult(
                    name="Configuration",
                    status="FAIL",
                    message=f"Empty required environment variables: {', '.join(empty_vars)}",
                    duration=time.time() - start_time,
                    details={"empty_vars": empty_vars}
                )

            # Check configuration file
            env_file = '.env'
            if not os.path.exists(env_file):
                return ValidationResult(
                    name="Configuration",
                    status="WARN",
                    message=f"Environment file {env_file} not found",
                    duration=time.time() - start_time,
                    critical=False
                )

            return ValidationResult(
                name="Configuration",
                status="PASS",
                message="All required configuration variables are present",
                duration=time.time() - start_time,
                details={"env_file": env_file}
            )

        except Exception as e:
            return ValidationResult(
                name="Configuration",
                status="FAIL",
                message=f"Configuration validation failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_network_connectivity(self) -> ValidationResult:
        """Validate network connectivity"""
        start_time = time.time()

        try:
            # Check port availability
            import socket

            unavailable_ports = []
            for port in self.requirements.required_ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result == 0:  # Port is open
                    continue
                else:  # Port is closed
                    unavailable_ports.append(port)

            if unavailable_ports:
                return ValidationResult(
                    name="Network Connectivity",
                    status="WARN",
                    message=f"Services not running on ports: {unavailable_ports}",
                    duration=time.time() - start_time,
                    critical=False,
                    details={"unavailable_ports": unavailable_ports}
                )

            return ValidationResult(
                name="Network Connectivity",
                status="PASS",
                message="All required ports are accessible",
                duration=time.time() - start_time,
                details={"checked_ports": self.requirements.required_ports}
            )

        except Exception as e:
            return ValidationResult(
                name="Network Connectivity",
                status="FAIL",
                message=f"Network connectivity check failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_service_health(self) -> ValidationResult:
        """Validate service health"""
        start_time = time.time()

        try:
            services = [
                ("API Gateway", self.config['api_gateway_url'] + "/health"),
                ("Webhook Handler", self.config['webhook_url'] + "/health"),
                ("Ingestion Service", self.config['ingestion_url'] + "/health"),
                ("Embedding Service", self.config['embedding_url'] + "/health"),
                ("Query Service", self.config['query_url'] + "/health"),
                ("LLM Service", self.config['llm_url'] + "/health"),
                ("Frontend", self.config['frontend_url'])
            ]

            unhealthy_services = []
            healthy_services = []

            for service_name, health_url in services:
                try:
                    response = await self.session.get(health_url, timeout=10.0)
                    if response.status_code == 200:
                        healthy_services.append(service_name)
                    else:
                        unhealthy_services.append(f"{service_name} (HTTP {response.status_code})")
                except Exception as e:
                    unhealthy_services.append(f"{service_name} (Error: {str(e)})")

            if unhealthy_services:
                return ValidationResult(
                    name="Service Health",
                    status="FAIL",
                    message=f"Unhealthy services: {', '.join(unhealthy_services)}",
                    duration=time.time() - start_time,
                    details={
                        "healthy_services": healthy_services,
                        "unhealthy_services": unhealthy_services
                    }
                )

            return ValidationResult(
                name="Service Health",
                status="PASS",
                message=f"All {len(healthy_services)} services are healthy",
                duration=time.time() - start_time,
                details={"healthy_services": healthy_services}
            )

        except Exception as e:
            return ValidationResult(
                name="Service Health",
                status="FAIL",
                message=f"Service health check failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_database_connectivity(self) -> ValidationResult:
        """Validate database connectivity"""
        start_time = time.time()

        try:
            # Test PostgreSQL connection
            self.db_pool = await asyncpg.create_pool(
                self.config['database_url'],
                min_size=1,
                max_size=2,
                command_timeout=10
            )

            async with self.db_pool.acquire() as conn:
                # Test basic query
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    raise Exception("Database query returned unexpected result")

                # Check if required tables exist
                tables = await conn.fetch("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                """)

                table_names = [row['tablename'] for row in tables]
                required_tables = ['doctype_configs']
                missing_tables = [t for t in required_tables if t not in table_names]

                if missing_tables:
                    return ValidationResult(
                        name="Database Connectivity",
                        status="WARN",
                        message=f"Missing tables: {', '.join(missing_tables)}",
                        duration=time.time() - start_time,
                        critical=False,
                        details={"missing_tables": missing_tables}
                    )

            return ValidationResult(
                name="Database Connectivity",
                status="PASS",
                message="Database connection successful",
                duration=time.time() - start_time,
                details={"tables": table_names}
            )

        except Exception as e:
            return ValidationResult(
                name="Database Connectivity",
                status="FAIL",
                message=f"Database connection failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_redis_connectivity(self) -> ValidationResult:
        """Validate Redis connectivity"""
        start_time = time.time()

        try:
            self.redis_client = redis.from_url(self.config['redis_url'])

            # Test basic operations
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.ping
            )

            # Test set/get
            test_key = f"validation_test_{uuid.uuid4().hex}"
            test_value = "test_value"

            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.set, test_key, test_value, 'EX', 60
            )

            retrieved_value = await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.get, test_key
            )

            if retrieved_value.decode() != test_value:
                raise Exception("Redis get/set test failed")

            # Clean up
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.delete, test_key
            )

            return ValidationResult(
                name="Redis Connectivity",
                status="PASS",
                message="Redis connection and operations successful",
                duration=time.time() - start_time
            )

        except Exception as e:
            return ValidationResult(
                name="Redis Connectivity",
                status="FAIL",
                message=f"Redis connection failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_qdrant_connectivity(self) -> ValidationResult:
        """Validate Qdrant connectivity"""
        start_time = time.time()

        try:
            self.qdrant_client = QdrantClient(url=self.config['qdrant_url'])

            # Test basic operations
            collections = self.qdrant_client.get_collections()

            # Check if documents collection exists
            collection_names = [col.name for col in collections.collections]
            if 'documents' not in collection_names:
                return ValidationResult(
                    name="Qdrant Connectivity",
                    status="WARN",
                    message="Documents collection not found",
                    duration=time.time() - start_time,
                    critical=False,
                    details={"collections": collection_names}
                )

            # Test collection info
            collection_info = self.qdrant_client.get_collection('documents')

            return ValidationResult(
                name="Qdrant Connectivity",
                status="PASS",
                message="Qdrant connection successful",
                duration=time.time() - start_time,
                details={
                    "collections": collection_names,
                    "documents_collection": {
                        "vectors_count": collection_info.vectors_count,
                        "points_count": collection_info.points_count
                    }
                }
            )

        except Exception as e:
            return ValidationResult(
                name="Qdrant Connectivity",
                status="FAIL",
                message=f"Qdrant connection failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_ollama_connectivity(self) -> ValidationResult:
        """Validate Ollama connectivity"""
        start_time = time.time()

        try:
            # Test Ollama API
            response = await self.session.get(f"{self.config['ollama_url']}/api/tags")

            if response.status_code != 200:
                return ValidationResult(
                    name="Ollama Connectivity",
                    status="FAIL",
                    message=f"Ollama API returned {response.status_code}",
                    duration=time.time() - start_time
                )

            models = response.json()
            model_names = [model['name'] for model in models.get('models', [])]

            if not model_names:
                return ValidationResult(
                    name="Ollama Connectivity",
                    status="WARN",
                    message="No models found in Ollama",
                    duration=time.time() - start_time,
                    critical=False
                )

            return ValidationResult(
                name="Ollama Connectivity",
                status="PASS",
                message=f"Ollama connected with {len(model_names)} models",
                duration=time.time() - start_time,
                details={"models": model_names}
            )

        except Exception as e:
            return ValidationResult(
                name="Ollama Connectivity",
                status="FAIL",
                message=f"Ollama connection failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_security_configuration(self) -> ValidationResult:
        """Validate security configuration"""
        start_time = time.time()

        try:
            issues = []

            # Check JWT secret strength
            jwt_secret = self.config.get('jwt_secret', '')
            if len(jwt_secret) < 32:
                issues.append("JWT secret too short (< 32 characters)")

            # Check webhook secret strength
            webhook_secret = self.config.get('webhook_secret', '')
            if len(webhook_secret) < 16:
                issues.append("Webhook secret too short (< 16 characters)")

            # Check if running in production with development settings
            if self.config.get('environment') == 'production':
                if 'localhost' in self.config.get('database_url', ''):
                    issues.append("Using localhost database in production")
                if 'localhost' in self.config.get('redis_url', ''):
                    issues.append("Using localhost Redis in production")

            # Check for default passwords
            if 'dossier123' in self.config.get('database_url', ''):
                issues.append("Using default database password")

            if issues:
                return ValidationResult(
                    name="Security Configuration",
                    status="WARN",
                    message=f"Security issues: {'; '.join(issues)}",
                    duration=time.time() - start_time,
                    critical=False,
                    details={"issues": issues}
                )

            return ValidationResult(
                name="Security Configuration",
                status="PASS",
                message="Security configuration looks good",
                duration=time.time() - start_time
            )

        except Exception as e:
            return ValidationResult(
                name="Security Configuration",
                status="FAIL",
                message=f"Security validation failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def validate_performance_baseline(self) -> ValidationResult:
        """Validate performance baseline"""
        start_time = time.time()

        try:
            # Test basic query performance
            query_payload = {
                "query": "performance test",
                "top_k": 5,
                "include_metadata": True
            }

            query_start = time.time()
            response = await self.session.post(
                f"{self.config['query_url']}/api/search",
                json=query_payload,
                timeout=10.0
            )
            query_duration = time.time() - query_start

            if response.status_code != 200:
                return ValidationResult(
                    name="Performance Baseline",
                    status="FAIL",
                    message=f"Query performance test failed: HTTP {response.status_code}",
                    duration=time.time() - start_time
                )

            # Check response time
            if query_duration > 5.0:
                return ValidationResult(
                    name="Performance Baseline",
                    status="WARN",
                    message=f"Query response time too slow: {query_duration:.2f}s",
                    duration=time.time() - start_time,
                    critical=False,
                    details={"query_duration": query_duration}
                )

            return ValidationResult(
                name="Performance Baseline",
                status="PASS",
                message=f"Performance baseline acceptable: {query_duration:.2f}s query time",
                duration=time.time() - start_time,
                details={"query_duration": query_duration}
            )

        except Exception as e:
            return ValidationResult(
                name="Performance Baseline",
                status="FAIL",
                message=f"Performance baseline test failed: {str(e)}",
                duration=time.time() - start_time
            )

    async def run_all_validations(self) -> List[ValidationResult]:
        """Run all validation checks"""
        logger.info("Starting deployment validation...")

        validations = [
            self.validate_system_requirements(),
            self.validate_docker_environment(),
            self.validate_configuration(),
            self.validate_network_connectivity(),
            self.validate_service_health(),
            self.validate_database_connectivity(),
            self.validate_redis_connectivity(),
            self.validate_qdrant_connectivity(),
            self.validate_ollama_connectivity(),
            self.validate_security_configuration(),
            self.validate_performance_baseline()
        ]

        results = []
        for validation in validations:
            result = await validation
            self._add_result(result)
            results.append(result)

        return results

    def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        total_checks = len(self.results)
        passed_checks = sum(1 for r in self.results if r.status == "PASS")
        failed_checks = sum(1 for r in self.results if r.status == "FAIL")
        warned_checks = sum(1 for r in self.results if r.status == "WARN")

        critical_failures = sum(1 for r in self.results if r.status == "FAIL" and r.critical)

        report = f"""
{'='*80}
DOSSIER RAG SYSTEM - DEPLOYMENT VALIDATION REPORT
{'='*80}

Validation Timestamp: {datetime.now().isoformat()}
Environment: {self.config.get('environment', 'unknown')}

SUMMARY:
--------
Total Checks: {total_checks}
Passed: {passed_checks}
Failed: {failed_checks}
Warnings: {warned_checks}
Critical Failures: {critical_failures}

Overall Status: {"READY" if critical_failures == 0 else "NOT READY"}

DETAILED RESULTS:
-----------------
"""

        for result in self.results:
            status_symbol = {
                "PASS": "✓",
                "FAIL": "✗",
                "WARN": "⚠",
                "SKIP": "-"
            }.get(result.status, "?")

            report += f"{status_symbol} {result.name}: {result.status}\n"
            report += f"  Message: {result.message}\n"
            report += f"  Duration: {result.duration:.2f}s\n"

            if result.details:
                report += f"  Details: {json.dumps(result.details, indent=4)}\n"

            report += "\n"

        report += f"""
{'='*80}
DEPLOYMENT RECOMMENDATIONS:
{'='*80}
"""

        if critical_failures > 0:
            report += """
❌ DEPLOYMENT NOT READY
- Fix all critical failures before proceeding
- Review error messages and resolve issues
- Re-run validation after fixes
"""
        elif warned_checks > 0:
            report += """
⚠️  DEPLOYMENT READY WITH WARNINGS
- Address warnings for optimal performance
- Consider reviewing security settings
- Monitor system closely after deployment
"""
        else:
            report += """
✅ DEPLOYMENT READY
- All checks passed successfully
- System is ready for production use
- Consider regular health monitoring
"""

        report += f"""
{'='*80}
END OF REPORT
{'='*80}
"""

        return report

    def save_report(self, filename: str = "deployment-validation-report.txt"):
        """Save validation report to file"""
        report = self.generate_report()
        with open(filename, 'w') as f:
            f.write(report)
        logger.info(f"Validation report saved to {filename}")


async def main():
    """Main validation function"""
    import argparse

    parser = argparse.ArgumentParser(description="Dossier RAG System Deployment Validator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--output", default="deployment-validation-report.txt",
                       help="Output report file")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        async with DeploymentValidator(args.config) as validator:
            results = await validator.run_all_validations()

            # Generate and save report
            validator.save_report(args.output)

            # Print summary
            print(validator.generate_report())

            # Exit with appropriate code
            critical_failures = sum(1 for r in results if r.status == "FAIL" and r.critical)
            if critical_failures > 0:
                logger.error(f"Deployment validation failed with {critical_failures} critical failures")
                sys.exit(1)
            else:
                logger.info("Deployment validation completed successfully")
                sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Validation failed with unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
