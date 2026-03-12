"""
EduZim Shared Logging Library
=============================
Structured JSON logging for all microservices.

Usage:
    from eduzim_shared.logging import get_logger, setup_logging

    setup_logging(service_name="auth-service")
    logger = get_logger(__name__)
    logger.info("User registered", extra={"user_id": "...", "school_id": "..."})
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON for machine parsing."""

    def __init__(self, service_name: str = "eduzim"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include extra fields (user_id, school_id, request_id, etc.)
        reserved = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "thread", "threadName", "exc_info", "exc_text",
            "getMessage", "message", "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved and not key.startswith("_"):
                log_entry[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, default=str)


_configured = False


def setup_logging(
    service_name: str = "eduzim",
    level: int = logging.INFO,
    json_output: bool = True,
) -> None:
    """
    Configure root logger for the service.
    Call once at service startup.

    Args:
        service_name: Name of the microservice (e.g., "auth-service")
        level: Logging level (default INFO)
        json_output: If True, output structured JSON; else plain text
    """
    global _configured
    if _configured:
        return
    _configured = True

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(JSONFormatter(service_name=service_name))
    else:
        handler.setFormatter(logging.Formatter(
            f"%(asctime)s [{service_name}] %(levelname)-8s %(name)s: %(message)s"
        ))

    root_logger.addHandler(handler)

    # Reduce noise from third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
