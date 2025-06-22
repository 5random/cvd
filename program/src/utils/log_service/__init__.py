"""
CVD Tracker Logging Service

This module provides comprehensive logging functionality for the CVD Tracker application.
It includes separate loggers for different types of messages, configuration-driven settings,
log rotation, and specialized logging for experiments, sensors, controllers, and data processing.

Features:
- Separate logs for info, error/warning, performance, audit, and structured data
- Configuration loading from config.json via config_service
- Log rotation with size and time-based policies
- JSON structured logging with context tracking
- Performance timing and audit logging
- Maintenance functions for cleanup and rotation
- Context managers for easier logging
- Global instance pattern with convenience functions
"""

import logging
import logging.handlers
import os
import json
import time
import threading
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union, List, Iterator
from contextlib import contextmanager
from enum import Enum

from program.src.utils.config_service import (
    get_config_service,
    set_config_service,
    ConfigurationError,
    ConfigurationService,
)  # type: ignore

from .maintenance import rotate_logs, cleanup_old_logs, compress_old_logs


class LogLevel(Enum):
    """Log level enumeration"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext:
    """Context for tracking logging sessions and requests"""

    def __init__(self):
        self._context = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any) -> None:
        """Set context value"""
        with self._lock:
            self._context[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get context value"""
        with self._lock:
            return self._context.get(key, default)

    def update(self, context: Dict[str, Any]) -> None:
        """Update context with dictionary"""
        with self._lock:
            self._context.update(context)

    def clear(self) -> None:
        """Clear all context"""
        with self._lock:
            self._context.clear()

    def copy(self) -> Dict[str, Any]:
        """Get copy of current context"""
        with self._lock:
            return self._context.copy()


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""

    def __init__(self, context: LogContext):
        super().__init__()
        self.context = context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context
        context = self.context.copy()
        if context:
            log_entry["context"] = context

        # Add extra fields if present
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            log_entry.update(extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class LogService:
    """
    Comprehensive logging service for CVD Tracker application.
    """

    # Pylance: ensure config_service is recognized as non-optional
    config_service: ConfigurationService

    def __init__(self, config_service: Optional[ConfigurationService] = None):
        """Create a new :class:`LogService`.

        If ``config_service`` is not provided and no global configuration
        service has been set, this constructor attempts to initialise a default
        :class:`ConfigurationService` using the repository's ``config``
        directory.  This mirrors the behaviour expected by the tests where no
        explicit configuration is created before the logger is accessed.
        """

        service = config_service or get_config_service()
        if service is None:
            # Lazily create a configuration service so that ``get_log_service``
            # works even when the caller has not initialised one explicitly.
            repo_root = Path(__file__).resolve().parents[3]
            config_path = repo_root / "config" / "config.json"
            default_config_path = repo_root / "config" / "default_config.json"
            try:
                service = ConfigurationService(config_path, default_config_path)
                set_config_service(service)
            except Exception as exc:
                raise ConfigurationError(
                    f"LogService failed to initialise ConfigurationService: {exc}"
                ) from exc

        self.config_service = service
        self.log_context = LogContext()
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        self._initialized = False
        self._lock = threading.Lock()

        # Initialize logging
        self._initialize_logging()

    def _initialize_logging(self) -> None:
        """Initialize all loggers and handlers"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # Load configuration with proper defaults
            self.log_level = (
                self.config_service.get("logging.level", default="INFO") or "INFO"
            )
            log_dir_config = self.config_service.get(
                "logging.log_dir", default="data/logs"
            )
            self.log_dir = Path(log_dir_config) if log_dir_config else Path("data/logs")
            rotation_value = (
                self.config_service.get("logging.log_file_rotation_mb", default=10)
                or 10
            )
            self.rotation_mb = int(rotation_value)
            retention_value = (
                self.config_service.get("logging.retention_days", default=30) or 30
            )
            self.retention_days = int(retention_value)

            # Create log directory
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # Setup loggers
            self._setup_info_logger()
            self._setup_error_logger()
            self._setup_performance_logger()
            self._setup_audit_logger()
            self._setup_structured_logger()
            self._initialized = True

    def _setup_info_logger(self) -> None:
        """Setup info logger for general information"""
        logger = logging.getLogger("cvd_tracker.info")
        # Safely get log level with proper type handling
        log_level_str = self.log_level or "INFO"
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setLevel(log_level)
        logger.handlers.clear()

        # Rotating file handler
        info_file = self.log_dir / "info.log"
        handler = logging.handlers.RotatingFileHandler(
            info_file,
            maxBytes=self.rotation_mb * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )

        # Format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        self._loggers["info"] = logger
        self._handlers["info"] = handler

    def _setup_error_logger(self) -> None:
        """Setup error/warning logger"""
        logger = logging.getLogger("cvd_tracker.error")
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()

        # Rotating file handler
        error_file = self.log_dir / "error.log"
        handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=self.rotation_mb * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )

        # Format with more details for errors
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        self._loggers["error"] = logger
        self._handlers["error"] = handler

    def _setup_performance_logger(self) -> None:
        """Setup performance logger"""
        logger = logging.getLogger("cvd_tracker.performance")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Timed rotating file handler (daily)
        perf_file = self.log_dir / "performance.log"
        handler = logging.handlers.TimedRotatingFileHandler(
            perf_file,
            when="midnight",
            interval=1,
            backupCount=self.retention_days,
            encoding="utf-8",
        )

        # Format for performance metrics
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        self._loggers["performance"] = logger
        self._handlers["performance"] = handler

    def _setup_audit_logger(self) -> None:
        """Setup audit logger"""
        logger = logging.getLogger("cvd_tracker.audit")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Timed rotating file handler (daily)
        audit_file = self.log_dir / "audit.log"
        handler = logging.handlers.TimedRotatingFileHandler(
            audit_file,
            when="midnight",
            interval=1,
            backupCount=self.retention_days,
            encoding="utf-8",
        )

        # Format for audit trails
        formatter = logging.Formatter(
            "%(asctime)s - AUDIT - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        self._loggers["audit"] = logger
        self._handlers["audit"] = handler

    def _setup_structured_logger(self) -> None:
        """Setup structured logger for JSON output"""
        logger = logging.getLogger("cvd_tracker.structured")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Timed rotating file handler (daily)
        structured_file = self.log_dir / "structured.log"
        handler = logging.handlers.TimedRotatingFileHandler(
            structured_file,
            when="midnight",
            interval=1,
            backupCount=self.retention_days,
            encoding="utf-8",
        )
        # Use structured formatter
        formatter = StructuredFormatter(self.log_context)
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        self._loggers["structured"] = logger
        self._handlers["structured"] = handler

    # Core logging methods
    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        if "info" in self._loggers:
            self._loggers["info"].info(message, extra=kwargs, stacklevel=2)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        if "error" in self._loggers:
            self._loggers["error"].warning(message, extra=kwargs, stacklevel=2)

    def error(self, message: str, exc_info=None, **kwargs) -> None:
        """Log error message"""
        if "error" in self._loggers:
            self._loggers["error"].error(
                message,
                exc_info=exc_info,
                extra=kwargs,
                stacklevel=2,
            )

    def critical(self, message: str, exc_info=None, **kwargs) -> None:
        """Log critical message"""
        if "error" in self._loggers:
            self._loggers["error"].critical(
                message,
                exc_info=exc_info,
                extra=kwargs,
                stacklevel=2,
            )

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        if "info" in self._loggers:
            self._loggers["info"].debug(message, extra=kwargs, stacklevel=2)

    # Specialized logging methods
    def log_experiment_event(
        self,
        event_type: str,
        experiment_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log experiment-related events"""
        message = f"Experiment {event_type}: {experiment_id}"
        if details:
            message += f" - {details}"
        self.info(
            message, experiment_id=experiment_id, event_type=event_type, details=details
        )
        # Also log to audit trail
        self.audit(
            f"EXPERIMENT_{event_type.upper()}",
            {"experiment_id": experiment_id, "details": details or {}},
        )

    def log_sensor_event(
        self, sensor_id: str, event_type: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log sensor-related events"""
        message = f"Sensor {event_type}: {sensor_id}"
        if data:
            message += f" - Data: {data}"
        self.info(message, sensor_id=sensor_id, event_type=event_type, sensor_data=data)

    def log_controller_event(
        self,
        controller_id: str,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log controller actions"""
        message = f"Controller {action}: {controller_id}"
        if parameters:
            message += f" - Parameters: {parameters}"
        self.info(
            message, controller_id=controller_id, action=action, parameters=parameters
        )

    def log_data_processing(
        self,
        process_type: str,
        input_data: Any,
        output_data: Any = None,
        processing_time: Optional[float] = None,
    ) -> None:
        """Log data processing events"""
        message = f"Data processing: {process_type}"
        if processing_time:
            message += f" (took {processing_time:.3f}s)"

        extra_fields = {
            "process_type": process_type,
            "input_size": len(str(input_data)) if input_data else 0,
            "processing_time": processing_time,
        }

        if output_data is not None:
            extra_fields["output_size"] = len(str(output_data))

        self.info(message, **extra_fields)

        # Performance logging
        if processing_time:
            self.performance(
                f"PROCESS_{process_type.upper()}", processing_time, extra_fields
            )

    # Performance logging
    def performance(
        self, operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log performance metrics"""
        message = f"{operation}: {duration:.3f}s"
        if metadata:
            message += f" | {metadata}"

        if "performance" in self._loggers:
            self._loggers["performance"].info(
                message,
                extra={
                    "operation": operation,
                    "duration": duration,
                    "metadata": metadata or {},
                },
            )

    @contextmanager
    def timer(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for timing operations"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.performance(operation, duration, metadata)

    # Audit logging
    def audit(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log audit events"""
        message = f"{action}"
        if details:
            message += f": {json.dumps(details, default=str)}"

        if "audit" in self._loggers:
            self._loggers["audit"].info(
                message,
                extra={
                    "action": action,
                    "details": details or {},
                    "timestamp": datetime.now().isoformat(),
                },
            )

    # Structured logging
    def structured(
        self, event: str, data: Optional[Dict[str, Any]] = None, level: str = "INFO"
    ) -> None:
        """Log structured data as JSON"""
        if "structured" in self._loggers:
            log_method = getattr(
                self._loggers["structured"],
                level.lower(),
                self._loggers["structured"].info,
            )
            log_method(event, extra={"extra_fields": data or {}})

    # Context management
    @contextmanager
    def logging_context(self, **kwargs) -> Iterator[None]:
        """Context manager for setting temporary context"""
        old_context = self.log_context.copy()
        try:
            self.log_context.update(kwargs)
            yield
        finally:
            self.log_context.clear()
            self.log_context.update(old_context)

    def set_context(self, **kwargs) -> None:
        """Set logging context"""
        self.log_context.update(kwargs)

    def clear_context(self) -> None:
        """Clear logging context"""
        self.log_context.clear()

    # Maintenance functions
    def rotate_logs(self) -> None:
        """Manually rotate all logs"""
        rotate_logs(self)

    def cleanup_old_logs(self) -> None:
        """Clean up old log files beyond retention period"""
        cleanup_old_logs(self)

    def compress_old_logs(self) -> None:
        """Compress old log files to save space"""
        compress_old_logs(self)

    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        log_files: list[Dict[str, Any]] = []
        stats: Dict[str, Any] = {
            "log_directory": str(self.log_dir),
            "log_level": self.log_level,
            "rotation_mb": self.rotation_mb,
            "retention_days": self.retention_days,
            "active_loggers": list(self._loggers.keys()),
            "log_files": log_files,
        }

        # Get file stats
        for log_file in self.log_dir.glob("*.log*"):
            file_stat = log_file.stat()
            log_files.append(
                {
                    "name": log_file.name,
                    "size_mb": file_stat.st_size / (1024 * 1024),
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                }
            )

        return stats


# Global instance
_log_service_instance: Optional[LogService] = None
_instance_lock = threading.Lock()


def get_log_service() -> LogService:
    """Get the global log service instance"""
    global _log_service_instance
    if _log_service_instance is None:
        with _instance_lock:
            if _log_service_instance is None:
                _log_service_instance = LogService()
    return _log_service_instance


# Convenience functions
def info(message: str, **kwargs):
    """Log info message using global instance"""
    get_log_service().info(message, **kwargs)


def warning(message: str, **kwargs):
    """Log warning message using global instance"""
    get_log_service().warning(message, **kwargs)


def error(message: str, exc_info=None, **kwargs):
    """Log error message using global instance"""
    get_log_service().error(message, exc_info=exc_info, **kwargs)


def critical(message: str, exc_info=None, **kwargs):
    """Log critical message using global instance"""
    get_log_service().critical(message, exc_info=exc_info, **kwargs)


def debug(message: str, **kwargs):
    """Log debug message using global instance"""
    get_log_service().debug(message, **kwargs)


def audit(action: str, details: Optional[Dict[str, Any]] = None):
    """Log audit event using global instance"""
    get_log_service().audit(action, details)


def performance(
    operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None
):
    """Log performance metric using global instance"""
    get_log_service().performance(operation, duration, metadata)


def timer(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Timer context manager using global instance"""
    return get_log_service().timer(operation, metadata)


def context(**kwargs):
    """Context manager using global instance"""
    return get_log_service().logging_context(**kwargs)


def log_experiment_event(
    event_type: str, experiment_id: str, details: Optional[Dict[str, Any]] = None
):
    """Log experiment event using global instance"""
    get_log_service().log_experiment_event(event_type, experiment_id, details)


def log_sensor_event(
    sensor_id: str, event_type: str, data: Optional[Dict[str, Any]] = None
):
    """Log sensor event using global instance"""
    get_log_service().log_sensor_event(sensor_id, event_type, data)


def log_controller_event(
    controller_id: str, action: str, parameters: Optional[Dict[str, Any]] = None
):
    """Log controller event using global instance"""
    get_log_service().log_controller_event(controller_id, action, parameters)


def log_data_processing(
    process_type: str,
    input_data: Any,
    output_data: Any = None,
    processing_time: Optional[float] = None,
):
    """Log data processing using global instance"""
    get_log_service().log_data_processing(
        process_type, input_data, output_data, processing_time
    )


# Basic global convenience functions
def log_info(message: str, **kwargs):
    """Log info message using global instance"""
    get_log_service().info(message, **kwargs)


def log_error(message: str, **kwargs):
    """Log error message using global instance"""
    get_log_service().error(message, **kwargs)


def log_performance(task_name: str, duration: float, **kwargs):
    """Log performance metric using global instance"""
    get_log_service().performance(task_name, duration, **kwargs)


def log_audit(action: str, data: Dict[str, Any]):
    """Log audit event using global instance"""
    get_log_service().audit(action, data)


def log_structured(event_type: str, data: Dict[str, Any]):
    """Log structured data using global instance"""
    get_log_service().structured(event_type, data)


module = sys.modules[__name__]
sys.modules.setdefault("program.src.utils.log_service", module)
sys.modules.setdefault("src.utils.log_service", module)
