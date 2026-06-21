from __future__ import annotations

import importlib
import json
import logging
import sys
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from types import ModuleType
from typing import Any, Protocol, cast

STRUCTLOG_MODULE = "structlog"


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


def _load_structlog() -> ModuleType | None:
    try:
        return importlib.import_module(STRUCTLOG_MODULE)
    except ImportError:
        return None


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog_module = _load_structlog()

    if structlog_module is None:
        return

    structlog_module.configure(
        processors=[
            structlog_module.contextvars.merge_contextvars,
            structlog_module.processors.TimeStamper(fmt="iso"),
            structlog_module.processors.add_log_level,
            structlog_module.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog_module.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog_module.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> LoggerProtocol:
    structlog_module = _load_structlog()

    if structlog_module is None:
        return JsonFallbackLogger(name)

    return cast(LoggerProtocol, structlog_module.get_logger(name))


@contextmanager
def log_stage(
    logger: LoggerProtocol,
    stage: str,
    **fields: Any,
) -> Generator[str, None, None]:
    started = time.perf_counter()
    stage_id = fields.pop("stage_id", f"stage-{uuid.uuid4().hex[:10]}")

    logger.info("stage.start", stage=stage, stage_id=stage_id, **fields)

    try:
        yield stage_id
        logger.info(
            "stage.success",
            stage=stage,
            stage_id=stage_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            **fields,
        )
    except Exception as exc:
        logger.exception(
            "stage.error",
            stage=stage,
            stage_id=stage_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error=repr(exc),
            **fields,
        )
        raise
