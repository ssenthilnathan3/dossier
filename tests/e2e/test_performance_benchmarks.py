"""
Performance benchmarks for the Dossier RAG system.
Tests system performance under various load conditions and measures key metrics.
"""

import os
import time
import asyncio
import pytest
import httpx
import json
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import concurrent.futures
from contextlib import asynccontextmanager

# Configuration
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:3001/webhooks/frappe")
INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8001")
QUERY_URL = os.getenv("QUERY_URL", "http://localhost:8003")
LLM_URL = os.getenv("LLM_URL", "http://localhost:8004")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://localhost:8002")

# Benchmark configuration
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhooksecret")


@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Benchmark result summary"""
    test_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration: float
    min_duration: float
    max_duration: float
    avg_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    throughput: float  # operations per second
    error_rate: float  # percentage
    metrics: List[PerformanceMetrics] = field(default_factory=list)


class PerformanceBenchmarker:
    """Performance benchmarking utility"""

    def __init__(self):
        self.session = httpx.AsyncClient(timeout=60.0)
        self.jwt_token = None
        self.results: List[BenchmarkResult] = []

    async def __aenter__(self):
        await self.generate_jwt_token()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()

    async def generate_jwt_token(self):
        """Generate JWT token for authentication"""
        import jwt
        payload = {
            "user_id": "benchmark_user",
            "exp": int(time.time()) + 7200,  # 2 hours
            "iat": int(time.time()),
            "sub": "benchmark_user"
        }
        self.jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def measure_operation(self, operation: str, func, *args, **kwargs) -> PerformanceMetrics:
        """Measure the performance of a single operation"""
        start_time = time.time()
        success = False
        error = None
        metadata = {}

        try:
            result = await func(*args, **kwargs)
            success = True
            if isinstance(result, dict):
                metadata = result
        except Exception as e:
            error = str(e)
            success = False

        end_time = time.time()
        duration = end_time - start_time

        return PerformanceMetrics(
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=success,
            error=error,
            metadata=metadata
        )

    async def run_concurrent_benchmark(
        self,
        test_name: str,
        operation_name: str,
        func,
        args_list: List[tuple],
        max_concurrent: int = 10
    ) -> BenchmarkResult:
        """Run concurrent operations and measure performance"""
        metrics = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(args):
            async with semaphore:
                return await self.measure_operation(operation_name, func, *args)

        # Create tasks
        tasks = [run_with_semaphore(args) for args in args_list]

        # Execute all tasks concurrently
        benchmark_start = time.time()
        metrics = await asyncio.gather(*tasks)
        benchmark_end = time.time()

        # Calculate statistics
        durations = [m.duration for m in metrics]
        successful_ops = [m for m in metrics if m.success]
        failed_ops = [m for m in metrics if not m.success]

        result = BenchmarkResult(
            test_name=test_name,
            total_operations=len(metrics),
            successful_operations=len(successful_ops),
            failed_operations=len(failed_ops),
            total_duration=benchmark_end - benchmark_start,
            min_duration=min(durations) if durations else 0,
            max_duration=max(durations) if durations else 0,
            avg_duration=statistics.mean(durations) if durations else 0,
            median_duration=statistics.median(durations) if durations else 0,
            p95_duration=statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else 0,
            p99_duration=statistics.quantiles(durations, n=100)[98] if len(durations) > 1 else 0,
            throughput=len(successful_ops) / (benchmark_end - benchmark_start),
            error_rate=(len(failed_ops) / len(metrics)) * 100,
            metrics=metrics
        )

        self.results.append(result)
        return result

    async def query_documents(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Query documents"""
        payload = {
            "query": query,
            "top_k": top_k,
            "include_metadata": True
        }

        response = await self.session.post(f"{QUERY_URL}/api/search", json=payload)
        response.raise_for_status()
        return response.json()

    async def generate_llm_response(self, query: str, context_chunks: List[Dict] = None) -> Dict[str, Any]:
        """Generate LLM response"""
        payload = {
            "query": query,
            "context_chunks": context_chunks or [],
            "model": "llama2",
            "temperature": 0.7
        }

        headers = self.get_auth_headers()
        response = await self.session.post(f"{API_GATEWAY_URL}/llm", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def embed_text(self, text: str) -> Dict[str, Any]:
        """Embed text"""
        payload = {"text": text}
        response = await self.session.post(f"{EMBEDDING_URL}/embed", json=payload)
        response.raise_for_status()
        return response.json()

    async def send_webhook(self, doctype: str, docname: str, content: str) -> Dict[str, Any]:
        """Send webhook"""
        import hmac
        import hashlib

        payload = {
            "doctype": doctype,
            "docname": docname,
            "operation": "create",
            "doc": {
                "doctype": doctype,
                "name": docname,
                "title": f"Test Document {docname}",
                "content": content
            }
        }

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

        response = await self.session.post(WEBHOOK_URL, json=payload, headers=headers)
        response.raise_for_status()
        return {"status": "success"}

    def print_benchmark_summary(self, result: BenchmarkResult):
        """Print benchmark summary"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {result.test_name}")
        print(f"{'='*60}")
        print(f"Total Operations: {result.total_operations}")
        print(f"Successful: {result.successful_operations}")
        print(f"Failed: {result.failed_operations}")
        print(f"Success Rate: {((result.successful_operations / result.total_operations) * 100):.1f}%")
        print(f"Error Rate: {result.error_rate:.1f}%")
        print(f"Total Duration: {result.total_duration:.2f}s")
        print(f"Throughput: {result.throughput:.2f} ops/sec")
        print(f"\nLatency Statistics:")
        print(f"  Min: {result.min_duration:.3f}s")
        print(f"  Max: {result.max_duration:.3f}s")
        print(f"  Avg: {result.avg_duration:.3f}s")
        print(f"  Median: {result.median_duration:.3f}s")
        print(f"  P95: {result.p95_duration:.3f}s")
        print(f"  P99: {result.p99_duration:.3f}s")
        print(f"{'='*60}")


@pytest.fixture
async def benchmarker():
    """Create performance benchmarker"""
    async with PerformanceBenchmarker() as client:
        yield client


@pytest.mark.asyncio
async def test_query_performance_light_load(benchmarker: PerformanceBenchmarker):
    """Test query performance under light load"""
    queries = [
        "machine learning algorithms",
        "API design principles",
        "container deployment",
        "database optimization",
        "microservices architecture"
    ]

    args_list = [(query,) for query in queries * 4]  # 20 queries total

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Query Performance - Light Load",
        operation_name="query_documents",
        func=benchmarker.query_documents,
        args_list=args_list,
        max_concurrent=5
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 5.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 2.0, f"Average query time too slow: {result.avg_duration}s"
    assert result.throughput > 2.0, f"Throughput too low: {result.throughput} ops/sec"


@pytest.mark.asyncio
async def test_query_performance_heavy_load(benchmarker: PerformanceBenchmarker):
    """Test query performance under heavy load"""
    queries = [
        "artificial intelligence",
        "software development",
        "data analysis",
        "system design",
        "performance optimization",
        "security best practices",
        "cloud computing",
        "database management"
    ]

    args_list = [(query,) for query in queries * 10]  # 80 queries total

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Query Performance - Heavy Load",
        operation_name="query_documents",
        func=benchmarker.query_documents,
        args_list=args_list,
        max_concurrent=20
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 10.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 5.0, f"Average query time too slow: {result.avg_duration}s"
    assert result.throughput > 5.0, f"Throughput too low: {result.throughput} ops/sec"


@pytest.mark.asyncio
async def test_llm_performance_sequential(benchmarker: PerformanceBenchmarker):
    """Test LLM performance with sequential requests"""
    questions = [
        "What is machine learning?",
        "How do APIs work?",
        "What are microservices?",
        "Explain containerization",
        "What is a database?"
    ]

    args_list = [(question,) for question in questions]

    result = await benchmarker.run_concurrent_benchmark(
        test_name="LLM Performance - Sequential",
        operation_name="generate_llm_response",
        func=benchmarker.generate_llm_response,
        args_list=args_list,
        max_concurrent=1  # Sequential
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 5.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 30.0, f"Average LLM time too slow: {result.avg_duration}s"


@pytest.mark.asyncio
async def test_llm_performance_concurrent(benchmarker: PerformanceBenchmarker):
    """Test LLM performance with concurrent requests"""
    questions = [
        "What is artificial intelligence?",
        "How does machine learning work?",
        "What are neural networks?",
        "Explain deep learning",
        "What is natural language processing?"
    ]

    args_list = [(question,) for question in questions]

    result = await benchmarker.run_concurrent_benchmark(
        test_name="LLM Performance - Concurrent",
        operation_name="generate_llm_response",
        func=benchmarker.generate_llm_response,
        args_list=args_list,
        max_concurrent=3  # Limited concurrency for LLM
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 10.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 45.0, f"Average LLM time too slow: {result.avg_duration}s"


@pytest.mark.asyncio
async def test_embedding_performance(benchmarker: PerformanceBenchmarker):
    """Test embedding service performance"""
    texts = [
        "Machine learning is a subset of artificial intelligence.",
        "APIs provide a way for applications to communicate.",
        "Microservices architecture breaks applications into small services.",
        "Containers provide lightweight application packaging.",
        "Databases store and manage structured data.",
        "Cloud computing provides on-demand computing resources.",
        "Security best practices protect against vulnerabilities.",
        "Performance optimization improves application speed."
    ]

    args_list = [(text,) for text in texts * 5]  # 40 embeddings total

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Embedding Performance",
        operation_name="embed_text",
        func=benchmarker.embed_text,
        args_list=args_list,
        max_concurrent=10
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 5.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 1.0, f"Average embedding time too slow: {result.avg_duration}s"
    assert result.throughput > 10.0, f"Throughput too low: {result.throughput} ops/sec"


@pytest.mark.asyncio
async def test_webhook_performance(benchmarker: PerformanceBenchmarker):
    """Test webhook processing performance"""
    content_templates = [
        "This is a test document about machine learning and artificial intelligence.",
        "API design principles and best practices for modern applications.",
        "Container orchestration with Docker and Kubernetes systems.",
        "Database optimization techniques for high-performance applications.",
        "Microservices architecture patterns and implementation strategies."
    ]

    args_list = [
        ("TestDoc", f"PERF-{i:03d}", content_templates[i % len(content_templates)])
        for i in range(20)
    ]

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Webhook Performance",
        operation_name="send_webhook",
        func=benchmarker.send_webhook,
        args_list=args_list,
        max_concurrent=5
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 5.0, f"Error rate too high: {result.error_rate}%"
    assert result.avg_duration < 2.0, f"Average webhook time too slow: {result.avg_duration}s"
    assert result.throughput > 5.0, f"Throughput too low: {result.throughput} ops/sec"


@pytest.mark.asyncio
async def test_mixed_workload_performance(benchmarker: PerformanceBenchmarker):
    """Test system performance under mixed workload"""
    # Mix of different operations
    operations = []

    # Add query operations
    for i in range(10):
        operations.append(("query", f"test query {i}"))

    # Add embedding operations
    for i in range(10):
        operations.append(("embed", f"test text for embedding {i}"))

    # Add LLM operations (fewer due to higher cost)
    for i in range(3):
        operations.append(("llm", f"test question {i}"))

    async def mixed_operation(op_type: str, data: str):
        if op_type == "query":
            return await benchmarker.query_documents(data)
        elif op_type == "embed":
            return await benchmarker.embed_text(data)
        elif op_type == "llm":
            return await benchmarker.generate_llm_response(data)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

    args_list = [(op_type, data) for op_type, data in operations]

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Mixed Workload Performance",
        operation_name="mixed_operation",
        func=mixed_operation,
        args_list=args_list,
        max_concurrent=8
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 10.0, f"Error rate too high: {result.error_rate}%"
    assert result.successful_operations > 20, f"Too few successful operations: {result.successful_operations}"


@pytest.mark.asyncio
async def test_sustained_load_performance(benchmarker: PerformanceBenchmarker):
    """Test system performance under sustained load"""
    queries = [
        "machine learning",
        "artificial intelligence",
        "data science",
        "software engineering",
        "system design"
    ]

    # Run for 60 seconds with steady load
    args_list = [(query,) for query in queries * 30]  # 150 queries

    result = await benchmarker.run_concurrent_benchmark(
        test_name="Sustained Load Performance",
        operation_name="query_documents",
        func=benchmarker.query_documents,
        args_list=args_list,
        max_concurrent=10
    )

    benchmarker.print_benchmark_summary(result)

    # Assertions
    assert result.error_rate < 5.0, f"Error rate too high: {result.error_rate}%"
    assert result.throughput > 3.0, f"Throughput too low: {result.throughput} ops/sec"
    assert result.p95_duration < 10.0, f"P95 latency too high: {result.p95_duration}s"


@pytest.mark.asyncio
async def test_generate_performance_report(benchmarker: PerformanceBenchmarker):
    """Generate comprehensive performance report"""
    # Calculate overall statistics
    total_operations = sum(r.total_operations for r in benchmarker.results)
    total_successful = sum(r.successful_operations for r in benchmarker.results)
    total_failed = sum(r.failed_operations for r in benchmarker.results)

    overall_success_rate = (total_successful / total_operations) * 100 if total_operations > 0 else 0
    overall_error_rate = (total_failed / total_operations) * 100 if total_operations > 0 else 0

    # Generate report
    report = {
        "summary": {
            "total_benchmarks": len(benchmarker.results),
            "total_operations": total_operations,
            "successful_operations": total_successful,
            "failed_operations": total_failed,
            "overall_success_rate": overall_success_rate,
            "overall_error_rate": overall_error_rate,
            "timestamp": datetime.now().isoformat()
        },
        "benchmarks": []
    }

    for result in benchmarker.results:
        benchmark_data = {
            "test_name": result.test_name,
            "total_operations": result.total_operations,
            "successful_operations": result.successful_operations,
            "failed_operations": result.failed_operations,
            "success_rate": (result.successful_operations / result.total_operations) * 100,
            "error_rate": result.error_rate,
            "total_duration": result.total_duration,
            "throughput": result.throughput,
            "latency_stats": {
                "min": result.min_duration,
                "max": result.max_duration,
                "avg": result.avg_duration,
                "median": result.median_duration,
                "p95": result.p95_duration,
                "p99": result.p99_duration
            }
        }
        report["benchmarks"].append(benchmark_data)

    # Save report
    report_path = "performance_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*80}")
    print("PERFORMANCE REPORT SUMMARY")
    print(f"{'='*80}")
    print(f"Total Benchmarks: {report['summary']['total_benchmarks']}")
    print(f"Total Operations: {report['summary']['total_operations']}")
    print(f"Overall Success Rate: {report['summary']['overall_success_rate']:.1f}%")
    print(f"Overall Error Rate: {report['summary']['overall_error_rate']:.1f}%")
    print(f"Report saved to: {report_path}")
    print(f"{'='*80}")

    # Performance assertions
    assert overall_success_rate > 90.0, f"Overall success rate too low: {overall_success_rate:.1f}%"
    assert overall_error_rate < 10.0, f"Overall error rate too high: {overall_error_rate:.1f}%"
