from __future__ import annotations

from typing import Any, Protocol

from app.observability.logging import get_logger, log_stage
from pydantic import BaseModel, Field

logger = get_logger("tools.retrieval")


class RetrieverProtocol(Protocol):
    """Structural contract for secure hybrid retrievers."""

    def retrieve(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        query: str,
        k: int = 8,
    ) -> list[dict[str, Any]]: ...


class RetrieveEvidenceInput(BaseModel):
    user_id: str = Field(
        min_length=1,
        description="The identity or role of the requesting user.",
    )
    opportunity_id: str = Field(
        min_length=1,
        description="The target strategic opportunity ID.",
    )
    query: str = Field(
        min_length=1,
        description="The search query derived from agent reasoning.",
    )
    k: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Token-budget guardrail for max retrieved chunks.",
    )


class RetrieveEvidenceTool:
    name: str = "retrieve_allowed_evidence"
    description: str = (
        "Performs secure hybrid RAG retrieval over permitted data. "
        "Enforces pre-retrieval scope validation based on user identity."
    )

    def __init__(
        self,
        retriever: RetrieverProtocol,
    ) -> None:
        self.retriever: RetrieverProtocol = retriever

    def run(
        self,
        request: RetrieveEvidenceInput,
    ) -> list[dict[str, Any]]:
        with log_stage(
            logger,
            "tool.retrieve_allowed_evidence",
            user_id=request.user_id,
            opportunity_id=request.opportunity_id,
            query=request.query,
            k=request.k,
        ):
            result: list[dict[str, Any]] = self.retriever.retrieve(
                user_id=request.user_id,
                opportunity_id=request.opportunity_id,
                query=request.query,
                k=request.k,
            )

            logger.info(
                "tool.retrieve_allowed_evidence.result",
                count=len(result),
                citations=[
                    {
                        "source": row.get("source_file", "unknown"),
                        "stable_id": row.get("stable_source_id", "unknown"),
                    }
                    for row in result
                ],
            )

            return result
