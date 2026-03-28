"""
Structured logging configuration for Skellington.

Learning goal: structlog for rich, structured, agent-aware logging.
"""

from __future__ import annotations

import logging
import sys

import structlog

from skellington.core.config import get_settings


def configure_logging() -> None:
    """Set up structlog with pretty console output for development."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
