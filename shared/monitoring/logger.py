"""
Structured JSON logging configuration for all services
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import traceback
import os


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def __init__(self, service_name: str, version: str = "1.0.0"):
        super().__init__()
        self.service_name = service_name
        self.version = version
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "version": self.version,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_entry["correlation_id"] = record.correlation_id
        
        # Add user ID if available
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, default=str)


def setup_logging(
    service_name: str,
    level: str = "INFO",
    version: str = "1.0.0"
) -> logging.Logger:
    """
    Set up structured JSON logging for a service
    
    Args:
        service_name: Name of the service
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        version: Service version
    
    Returns:
        Configured logger instance
    """
    # Get log level from environment or use provided level
    log_level = os.getenv("LOG_LEVEL", level).upper()
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name, version))
    logger.addHandler(handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger


class ContextLogger:
    """Logger wrapper that maintains context across requests"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set context variables for all subsequent log messages"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context variables"""
        self.context.clear()
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with current context"""
        extra = {**self.context, **kwargs}
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None, extra=extra
        )
        self.logger.handle(record)
    
    def debug(self, message: str, **kwargs):
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        kwargs['exc_info'] = True
        self._log_with_context(logging.ERROR, message, **kwargs)


def get_logger(service_name: str, level: str = "INFO") -> ContextLogger:
    """
    Get a context-aware logger for a service
    
    Args:
        service_name: Name of the service
        level: Logging level
    
    Returns:
        ContextLogger instance
    """
    base_logger = setup_logging(service_name, level)
    return ContextLogger(base_logger)