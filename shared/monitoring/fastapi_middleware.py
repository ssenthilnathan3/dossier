"""
FastAPI middleware for monitoring, logging, and tracing
"""
import time
import uuid
from typing import Callable, Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog

from .logger import get_logger
from .metrics import init_metrics, get_metrics_collector
from .tracing import init_tracer, get_tracer


# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'service']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'service']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Active HTTP requests',
    ['service']
)

ERROR_COUNT = Counter(
    'http_errors_total',
    'Total HTTP errors',
    ['method', 'endpoint', 'error_type', 'service']
)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for comprehensive monitoring"""
    
    def __init__(self, app: FastAPI, service_name: str):
        super().__init__(app)
        self.service_name = service_name
        self.logger = get_logger(service_name)
        
        # Initialize monitoring components
        init_metrics(service_name)
        init_tracer(service_name)
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate request context
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get('x-trace-id', str(uuid.uuid4()))
        correlation_id = request.headers.get('x-correlation-id')
        
        # Set request context
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.correlation_id = correlation_id
        request.state.start_time = time.time()
        
        # Set logger context
        self.logger.set_context(
            request_id=request_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            service=self.service_name
        )
        
        # Track active requests
        ACTIVE_REQUESTS.labels(service=self.service_name).inc()
        
        # Start tracing span
        tracer = get_tracer()
        span_context = {}
        if tracer:
            span_context = tracer.extract_headers(dict(request.headers))
        
        try:
            # Log request start
            self.logger.info("Request started", {
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None
            })
            
            # Process request
            if tracer:
                with tracer.span(
                    f"{request.method} {request.url.path}",
                    **span_context
                ) as span:
                    span.set_tag("http.method", request.method)
                    span.set_tag("http.url", str(request.url))
                    span.set_tag("service.name", self.service_name)
                    
                    response = await call_next(request)
                    
                    span.set_tag("http.status_code", response.status_code)
                    if response.status_code >= 400:
                        span.set_tag("error", True)
            else:
                response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - request.state.start_time
            
            # Record metrics
            endpoint = self._get_endpoint_pattern(request)
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
                service=self.service_name
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint,
                service=self.service_name
            ).observe(duration)
            
            # Log response
            self.logger.info("Request completed", {
                "status_code": response.status_code,
                "duration": duration,
                "response_size": response.headers.get("content-length", 0)
            })
            
            # Add response headers
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Trace-Id"] = trace_id
            
            return response
            
        except Exception as e:
            duration = time.time() - request.state.start_time
            endpoint = self._get_endpoint_pattern(request)
            
            # Record error metrics
            ERROR_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                error_type=type(e).__name__,
                service=self.service_name
            ).inc()
            
            # Log error
            self.logger.error("Request failed", {
                "error": str(e),
                "error_type": type(e).__name__,
                "duration": duration
            })
            
            raise
        
        finally:
            # Track active requests
            ACTIVE_REQUESTS.labels(service=self.service_name).dec()
            
            # Clear logger context
            self.logger.clear_context()
    
    def _get_endpoint_pattern(self, request: Request) -> str:
        """Extract endpoint pattern from request"""
        # Try to get the route pattern from FastAPI
        if hasattr(request, 'scope') and 'route' in request.scope:
            route = request.scope['route']
            if hasattr(route, 'path'):
                return route.path
        
        # Fallback to path
        return request.url.path


def setup_monitoring(app: FastAPI, service_name: str) -> FastAPI:
    """
    Set up comprehensive monitoring for a FastAPI application
    
    Args:
        app: FastAPI application instance
        service_name: Name of the service
    
    Returns:
        FastAPI app with monitoring configured
    """
    # Add monitoring middleware
    app.add_middleware(MonitoringMiddleware, service_name=service_name)
    
    # Add health check endpoint
    @app.get("/health")
    async def health_check(request: Request):
        """Health check endpoint with detailed status"""
        return {
            "status": "healthy",
            "service": service_name,
            "version": "1.0.0",
            "timestamp": time.time(),
            "request_id": getattr(request.state, 'request_id', None),
            "trace_id": getattr(request.state, 'trace_id', None)
        }
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus metrics endpoint"""
        metrics_collector = get_metrics_collector()
        if metrics_collector:
            custom_metrics = metrics_collector.get_metrics()
        else:
            custom_metrics = {}
        
        # Return Prometheus format metrics
        prometheus_metrics = generate_latest()
        
        return Response(
            content=prometheus_metrics,
            media_type=CONTENT_TYPE_LATEST,
            headers={"Custom-Metrics": str(custom_metrics)}
        )
    
    # Add tracing endpoint for debugging
    @app.get("/traces")
    async def traces_endpoint(limit: int = 10):
        """Get recent traces for debugging"""
        tracer = get_tracer()
        if not tracer:
            return {"traces": []}
        
        spans = tracer.get_spans(limit)
        return {
            "traces": [span.to_dict() for span in spans],
            "service": service_name,
            "timestamp": time.time()
        }
    
    return app


def get_request_context(request: Request) -> dict:
    """Get request context for logging and tracing"""
    return {
        "request_id": getattr(request.state, 'request_id', None),
        "trace_id": getattr(request.state, 'trace_id', None),
        "correlation_id": getattr(request.state, 'correlation_id', None),
        "method": request.method,
        "path": request.url.path
    }