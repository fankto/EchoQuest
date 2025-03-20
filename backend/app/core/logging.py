import os
import sys
import json
from datetime import datetime
from typing import Dict, Any

import loguru
from loguru import logger

from app.core.config import settings


class InterceptHandler(loguru.Handler):
    """
    Intercept standard logging messages toward loguru

    This handler intercepts all log records sent by the standard logging
    module and redirects them to loguru.
    """

    def emit(self, record: loguru.Record) -> None:
        # Get corresponding loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class JSONFormatter:
    """
    JSON formatter for loguru records

    Formats log records as JSON objects for structured logging.
    """

    def __call__(self, record: Dict[str, Any]) -> str:
        """
        Format the record as JSON

        Args:
            record: Log record

        Returns:
            JSON string
        """
        log_record = {
            "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "process_id": record["process"].id,
            "thread_id": record["thread"].id,
        }

        # Add exception info if present
        if record["exception"]:
            log_record["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback,
            }

        # Add extra fields
        if record["extra"]:
            log_record.update(record["extra"])

        return json.dumps(log_record)


def setup_logging() -> None:
    """
    Set up logging configuration

    Configures loguru logger with appropriate handlers and formatters
    based on the application environment.
    """
    # Remove default handler
    logger.remove()

    # Set log level based on environment
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # File for error logs
    error_log_file = os.path.join(log_dir, f"{settings.ENVIRONMENT}_error.log")

    # Add console handler
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        diagnose=True,
        backtrace=True,
        enqueue=True,
    )

    # Add file handler for errors
    logger.add(
        error_log_file,
        format=JSONFormatter() if settings.ENVIRONMENT == "production" else console_format,
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        diagnose=True,
        backtrace=True,
        enqueue=True,
    )

    # Add file handler for all logs in production/staging
    if settings.ENVIRONMENT in ["production", "staging"]:
        all_log_file = os.path.join(log_dir, f"{settings.ENVIRONMENT}_all.log")
        logger.add(
            all_log_file,
            format=JSONFormatter(),
            level=log_level,
            rotation="50 MB",
            retention="7 days",
            compression="zip",
            enqueue=True,
        )

    # Intercept standard logging
    import logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Update logging for commonly used libraries
    for logger_name in ["uvicorn", "uvicorn.error", "fastapi", "sqlalchemy.engine"]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]

    logger.info(f"Logging configured for {settings.ENVIRONMENT} environment at {log_level} level")


# Initialize logging when module is imported
setup_logging()