from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger, log_stage
from pydantic import BaseModel, Field

logger = get_logger("tools.retrieval")


class RetrieveEvidenceInput(BaseModel):
    user_id: str
    opportunity_id: str
    query: str = Field(min_length=3)
    k: int = 8


class RetrieveEvidenceTool:
    name: str = "retrieve_allowed_evidence"
    description: str = (
        "Hybrid RAG retrieval with permission filters before retrieval and before generation."
    )

    def __init__(self, retriever: Any) -> None:
        self.retriever: Any = retriever

    def run(self, inp: RetrieveEvidenceInput) -> list[dict[str, Any]]:
        with log_stage(
            logger,
            "tool.retrieve_allowed_evidence",
            user_id=inp.user_id,
            opportunity_id=inp.opportunity_id,
            query=inp.query,
            k=inp.k,
        ):
            result: list[dict[str, Any]] = self.retriever.retrieve(
                inp.user_id, inp.opportunity_id, inp.query, inp.k
            )
            logger.info(
                "tool.retrieve_allowed_evidence.result",
                count=len(result),
                citations=[
                    {"source": r["source_file"], "id": r["stable_source_id"]} for r in result
                ],
            )
            return result
