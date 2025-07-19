"""
Distributed tracing utilities for request flow tracking
"""
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import threading
from contextlib import contextmanager


@dataclass
class Span:
    """Represents a single span in a distributed trace"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok, error, timeout
    
    def finish(self):
        """Mark span as finished and calculate duration"""
        if self.end_time is None:
            self.end_time = time.time()
            self.duration = self.end_time - self.start_time
    
    def set_tag(self, key: str, value: Any):
        """Add a tag to the span"""
        self.tags[key] = value
    
    def log(self, message: str, **kwargs):
        """Add a log entry to the span"""
        log_entry = {
            "timestamp": time.time(),
            "message": message,
            **kwargs
        }
        self.logs.append(log_entry)
    
    def set_error(self, error: Exception):
        """Mark span as error and add error details"""
        self.status = "error"
        self.set_tag("error", True)
        self.set_tag("error.type", type(error).__name__)
        self.set_tag("error.message", str(error))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for serialization"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "tags": self.tags,
            "logs": self.logs,
            "status": self.status
        }


class TraceContext:
    """Thread-local trace context"""
    
    def __init__(self):
        self._local = threading.local()
    
    @property
    def current_span(self) -> Optional[Span]:
        """Get current active span"""
        return getattr(self._local, 'current_span', None)
    
    @current_span.setter
    def current_span(self, span: Optional[Span]):
        """Set current active span"""
        self._local.current_span = span
    
    @property
    def trace_id(self) -> Optional[str]:
        """Get current trace ID"""
        span = self.current_span
        return span.trace_id if span else None
    
    def clear(self):
        """Clear trace context"""
        self._local.current_span = None


class Tracer:
    """Distributed tracer for tracking request flows"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.context = TraceContext()
        self._spans: Dict[str, Span] = {}
        self._lock = threading.Lock()
    
    def start_span(
        self,
        operation_name: str,
        parent_span: Optional[Span] = None,
        trace_id: Optional[str] = None
    ) -> Span:
        """Start a new span"""
        # Use provided trace_id or generate new one
        if trace_id is None:
            if parent_span:
                trace_id = parent_span.trace_id
            elif self.context.current_span:
                trace_id = self.context.current_span.trace_id
            else:
                trace_id = str(uuid.uuid4())
        
        # Generate span ID
        span_id = str(uuid.uuid4())
        
        # Determine parent span ID
        parent_span_id = None
        if parent_span:
            parent_span_id = parent_span.span_id
        elif self.context.current_span:
            parent_span_id = self.context.current_span.span_id
        
        # Create span
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=self.service_name,
            start_time=time.time()
        )
        
        # Store span
        with self._lock:
            self._spans[span_id] = span
        
        return span
    
    def finish_span(self, span: Span):
        """Finish a span"""
        span.finish()
        
        # If this was the current span, clear it
        if self.context.current_span == span:
            self.context.current_span = None
    
    @contextmanager
    def span(self, operation_name: str, **tags):
        """Context manager for creating spans"""
        span = self.start_span(operation_name)
        
        # Add tags
        for key, value in tags.items():
            span.set_tag(key, value)
        
        # Set as current span
        previous_span = self.context.current_span
        self.context.current_span = span
        
        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            self.finish_span(span)
            self.context.current_span = previous_span
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace"""
        with self._lock:
            return [span for span in self._spans.values() if span.trace_id == trace_id]
    
    def get_spans(self, limit: int = 100) -> List[Span]:
        """Get recent spans"""
        with self._lock:
            spans = list(self._spans.values())
            # Sort by start time, most recent first
            spans.sort(key=lambda s: s.start_time, reverse=True)
            return spans[:limit]
    
    def clear_old_spans(self, max_age_seconds: int = 3600):
        """Clear spans older than max_age_seconds"""
        cutoff_time = time.time() - max_age_seconds
        
        with self._lock:
            old_span_ids = [
                span_id for span_id, span in self._spans.items()
                if span.start_time < cutoff_time
            ]
            
            for span_id in old_span_ids:
                del self._spans[span_id]
    
    def inject_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into HTTP headers"""
        current_span = self.context.current_span
        if current_span:
            headers = headers.copy()
            headers["X-Trace-Id"] = current_span.trace_id
            headers["X-Span-Id"] = current_span.span_id
        return headers
    
    def extract_headers(self, headers: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract trace context from HTTP headers"""
        trace_id = headers.get("X-Trace-Id") or headers.get("x-trace-id")
        span_id = headers.get("X-Span-Id") or headers.get("x-span-id")
        
        if trace_id:
            return {
                "trace_id": trace_id,
                "parent_span_id": span_id
            }
        
        return None


# Global tracer instance
_tracer: Optional[Tracer] = None


def init_tracer(service_name: str) -> Tracer:
    """Initialize global tracer"""
    global _tracer
    _tracer = Tracer(service_name)
    return _tracer


def get_tracer() -> Optional[Tracer]:
    """Get the global tracer"""
    return _tracer


def trace_operation(operation_name: str = "", **tags):
    """Decorator to trace function execution"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not _tracer:
                return func(*args, **kwargs)
            
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with _tracer.span(op_name, **tags) as span:
                # Add function info as tags
                span.set_tag("function.name", func.__name__)
                span.set_tag("function.module", func.__module__)
                
                return func(*args, **kwargs)
        
        return wrapper
    return decorator