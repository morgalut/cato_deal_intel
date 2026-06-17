from __future__ import annotations

import json
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.observability.logging import get_logger

logger = get_logger("trace")


@dataclass(slots=True)
class TraceBuffer:
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")

    events: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        event: dict[str, Any] = {
            "ts": time.time(),
            "run_id": self.run_id,
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        }

        self.events.append(event)

        logger.info(
            "trace.event",
            run_id=self.run_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
        )

    def dump_jsonl(self, path: str | Path) -> None:
        output_path = Path(path)

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file_handle:
            for event in self.events:
                file_handle.write(
                    json.dumps(
                        event,
                        ensure_ascii=False,
                    )
                    + "\n"
                )


@contextmanager
def traced(
    trace: TraceBuffer,
    actor: str,
    event_type: str,
    payload: dict[str, Any],
) -> Generator[None, None, None]:
    trace.add(
        f"{event_type}.start",
        actor,
        payload,
    )

    try:
        yield

        trace.add(
            f"{event_type}.success",
            actor,
            payload,
        )

    except Exception as exc:
        trace.add(
            f"{event_type}.error",
            actor,
            {
                **payload,
                "error": repr(exc),
            },
        )
        raise
