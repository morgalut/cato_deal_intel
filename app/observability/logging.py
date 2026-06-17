from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Protocol

try:
    import structlog  # type: ignore
except Exception:  # pragma: no cover
    structlog = None


class LoggerProtocol(Protocol):
    def info(self, event: str, **fields: Any) -> None: ...

    def exception(self, event: str, **fields: Any) -> None: ...


class JsonFallbackLogger:
    def __init__(self, name: str) -> None:
        self.name: str = name

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "logger": self.name,
            "level": level,
            "event": event,
            **fields,
        }

        print(json.dumps(payload, ensure_ascii=False))

    def info(self, event: str, **fields: Any) -> None:
        self._emit("info", event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit("error", event, **fields)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(
            logging,
            level.upper(),
            logging.INFO,
        ),
    )

    if structlog is None:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(
                ensure_ascii=False,
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(
                logging,
                level.upper(),
                logging.INFO,
            )
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> LoggerProtocol:
    if structlog is None:
        return JsonFallbackLogger(name)

    return structlog.get_logger(name)


@contextmanager
def log_stage(
    logger: LoggerProtocol,
    stage: str,
    **fields: Any,
) -> Generator[str, None, None]:
    """Log start/success/error/duration for a deterministic stage."""

    started: float = time.perf_counter()

    stage_id: str = fields.pop(
        "stage_id",
        f"stage-{uuid.uuid4().hex[:10]}",
    )

    logger.info(
        "stage.start",
        stage=stage,
        stage_id=stage_id,
        **fields,
    )

    try:
        yield stage_id

        logger.info(
            "stage.success",
            stage=stage,
            stage_id=stage_id,
            duration_ms=round(
                (time.perf_counter() - started) * 1000,
                2,
            ),
            **fields,
        )

    except Exception as exc:
        logger.exception(
            "stage.error",
            stage=stage,
            stage_id=stage_id,
            duration_ms=round(
                (time.perf_counter() - started) * 1000,
                2,
            ),
            error=repr(exc),
            **fields,
        )
        raise
