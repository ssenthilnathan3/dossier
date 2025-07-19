"""
Prometheus metrics collection for all services
"""
import time
from typing import Dict, List, Optional, Callable, Any
from functools import wraps
import threading
from collections import defaultdict, Counter
from datetime import datetime, timedelta


class MetricsCollector:
    """Thread-safe metrics collector for Prometheus-style metrics"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._lock = threading.Lock()
        
        # Counters: monotonically increasing values
        self._counters: Dict[str, float] = defaultdict(float)
        
        # Gauges: current values that can go up or down
        self._gauges: Dict[str, float] = defaultdict(float)
        
        # Histograms: track distributions of values
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        
        # Request tracking
        self._request_counts = Counter()
        self._request_durations: Dict[str, List[float]] = defaultdict(list)
        self._error_counts = Counter()
        
        # System metrics
        self._start_time = time.time()
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value"""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Add an observation to a histogram"""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Keep only last 1000 observations to prevent memory issues
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        labels = f"{method}:{endpoint}:{status_code}"
        
        with self._lock:
            self._request_counts[labels] += 1
            self._request_durations[labels].append(duration)
            
            if status_code >= 400:
                error_labels = f"{method}:{endpoint}"
                self._error_counts[error_labels] += 1
    
    def record_error(self, error_type: str, operation: str = ""):
        """Record error occurrence"""
        key = f"{error_type}:{operation}" if operation else error_type
        with self._lock:
            self._error_counts[key] += 1
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a key for metric storage"""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics in Prometheus format"""
        with self._lock:
            metrics = {
                "service": self.service_name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "uptime_seconds": time.time() - self._start_time,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "requests": {
                    "total": dict(self._request_counts),
                    "errors": dict(self._error_counts),
                    "durations": {}
                }
            }
            
            # Calculate histogram statistics
            for key, values in self._histograms.items():
                if values:
                    sorted_values = sorted(values)
                    count = len(sorted_values)
                    metrics["histograms"][key] = {
                        "count": count,
                        "sum": sum(sorted_values),
                        "min": sorted_values[0],
                        "max": sorted_values[-1],
                        "mean": sum(sorted_values) / count,
                        "p50": sorted_values[int(count * 0.5)],
                        "p95": sorted_values[int(count * 0.95)],
                        "p99": sorted_values[int(count * 0.99)]
                    }
            
            # Calculate request duration statistics
            for key, durations in self._request_durations.items():
                if durations:
                    sorted_durations = sorted(durations)
                    count = len(sorted_durations)
                    metrics["requests"]["durations"][key] = {
                        "count": count,
                        "mean": sum(sorted_durations) / count,
                        "p50": sorted_durations[int(count * 0.5)],
                        "p95": sorted_durations[int(count * 0.95)],
                        "p99": sorted_durations[int(count * 0.99)]
                    }
            
            return metrics


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def init_metrics(service_name: str) -> MetricsCollector:
    """Initialize global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(service_name)
    return _metrics_collector


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the global metrics collector"""
    return _metrics_collector


def timed(operation_name: str = "", labels: Optional[Dict[str, str]] = None):
    """Decorator to time function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if _metrics_collector:
                    _metrics_collector.observe_histogram(
                        "operation_duration_seconds",
                        duration,
                        {**(labels or {}), "operation": operation, "status": "success"}
                    )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                if _metrics_collector:
                    _metrics_collector.observe_histogram(
                        "operation_duration_seconds",
                        duration,
                        {**(labels or {}), "operation": operation, "status": "error"}
                    )
                    _metrics_collector.record_error(
                        error_type=type(e).__name__,
                        operation=operation
                    )
                
                raise
        
        return wrapper
    return decorator


def count_calls(metric_name: str = "", labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__name__}_calls_total"
            
            if _metrics_collector:
                _metrics_collector.increment_counter(name, 1.0, labels)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator