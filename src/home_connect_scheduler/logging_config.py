from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging (e.g. uvicorn's request/error logs) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(prefix: str) -> None:
    """Configure loguru to log to stderr and a rotating file under logs/."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", backtrace=False, diagnose=False)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    logger.add(
        log_dir / f"{prefix}_{timestamp}.log",
        level="DEBUG",
        rotation="10 MB",
        retention=10,
    )

    # Redirect stdlib logging (root + already-configured loggers like uvicorn's,
    # which attach their own handlers and set propagate=False) into loguru.
    logging.root.handlers = [_InterceptHandler()]
    logging.root.setLevel(logging.INFO)
    for name in logging.root.manager.loggerDict:
        existing = logging.getLogger(name)
        existing.handlers = []
        existing.propagate = True
