from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any, Literal, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

LangSmithRunType = Literal[
    "tool",
    "chain",
    "llm",
    "retriever",
    "embedding",
    "prompt",
    "parser",
]


def langsmith_enabled() -> bool:
    tracing_enabled = (
        os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        or os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    )

    has_key = bool(
        os.getenv("LANGSMITH_API_KEY")
        or os.getenv("LANGCHAIN_API_KEY")
    )

    return tracing_enabled and has_key


def traced(
    *,
    name: str,
    run_type: LangSmithRunType = "chain",
    metadata: Mapping[str, Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Optional LangSmith tracing wrapper.

    LangSmith is imported lazily so the application can run without it.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if not langsmith_enabled():
            return func

        try:
            from langsmith import traceable
        except ImportError:  # pragma: no cover
            return func

        wrapped = traceable(
            run_type,
            name=name,
            metadata=metadata or {},
        )(func)

        return cast(Callable[P, R], wrapped)

    return decorator
