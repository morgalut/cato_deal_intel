from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.observability.logging import get_logger, log_stage
from app.observability.tracing import TraceBuffer, traced

logger = get_logger("agents")


class AgentBase(ABC):
    name: str = "base_agent"
    system_contract: str = ""

    def __init__(self, trace: TraceBuffer, llm: Any | None = None) -> None:
        self.trace: TraceBuffer = trace
        self.llm: Any | None = llm

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe_payload: dict[str, Any] = {"input_keys": list(payload.keys())}

        with (
            traced(self.trace, self.name, "agent.invoke", safe_payload),
            log_stage(
                logger,
                "agent.invoke",
                agent=self.name,
                input_keys=list(payload.keys()),
            ),
        ):
            result: dict[str, Any] = self._run(payload)
            logger.info(
                "agent.output",
                agent=self.name,
                output_keys=list(result.keys()),
            )
            return result


    @abstractmethod
    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
