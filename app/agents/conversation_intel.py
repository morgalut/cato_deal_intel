from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentBase
from app.observability.tracing import TraceBuffer
from app.tools.retrieval_tools import RetrieveEvidenceInput


class ConversationIntelligenceAgent(AgentBase):
    name = "conversation_intelligence_agent"
    system_contract = (
        "LLM-backed extractor: extract buyer goals, objections, urgency, "
        "competitors, risks, missing information, and ambiguity only from "
        "allowed retrieved evidence. Every finding must include citation ids."
    )

    def __init__(
        self,
        trace: TraceBuffer,
        retrieval_tool: Any,
        llm: Any | None = None,
    ) -> None:
        super().__init__(trace, llm=llm)
        self.retrieval_tool: Any = retrieval_tool

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        docs: list[dict[str, Any]] = self.retrieval_tool.run(
            RetrieveEvidenceInput(
                user_id=payload["user_id"],
                opportunity_id=payload["opportunity_id"],
                query=(
                    "buyer goals objections risks next actions competitor "
                    "approval missing information slack gong"
                ),
                k=8,
            )
        )

        slack_docs: list[dict[str, Any]] = self.retrieval_tool.run(
            RetrieveEvidenceInput(
                user_id=payload["user_id"],
                opportunity_id=payload["opportunity_id"],
                query=("synthetic slack account team update ambiguity missing context reinforces"),
                k=4,
            )
        )

        seen: set[Any] = {doc["stable_source_id"] for doc in docs}
        docs += [doc for doc in slack_docs if doc["stable_source_id"] not in seen]

        llm_payload: dict[str, Any] | None = None

        if self.llm and docs:
            snippets: list[dict[str, Any]] = [
                {
                    "source": doc["source_file"],
                    "stable_source_id": doc["stable_source_id"],
                    "source_type": doc["source_type"],
                    "access": doc["source_access_level"],
                    "snippet": doc["content"][:900],
                }
                for doc in docs[:6]
            ]

            system: str = (
                "You are the Conversation Intelligence Agent for a sales "
                "negotiation brief. Use only the supplied evidence. Return "
                "JSON with findings[]. Each finding must include theme, "
                "finding, confidence, citations, conflict_or_ambiguity. "
                "Do not invent numbers, dates, stakeholders, discounts, or quotes."
            )

            user: str = json.dumps(
                {
                    "opportunity_id": payload["opportunity_id"],
                    "evidence": snippets,
                },
                ensure_ascii=False,
            )

            llm_payload, usage = self.llm.json_task(
                task="extraction",
                system=system,
                user=user,
                sensitivity=max(doc["source_access_level"] for doc in docs),
                max_tokens=900,
            )

            self.trace.add(
                "llm.extraction.complete",
                self.name,
                {
                    "model": usage.model,
                    "total_tokens": usage.total_tokens,
                    "offline": llm_payload.get("offline_mode", False),
                },
            )

        if llm_payload and isinstance(llm_payload.get("findings"), list):
            return {
                "findings": llm_payload["findings"],
                "evidence": docs,
                "llm_used": True,
            }

        findings: list[dict[str, Any]] = []

        for doc in docs[:5]:
            text: str = doc["content"][:360].replace("\n", " ")
            confidence: str = "medium"

            if (
                "conflict" in text.lower()
                or "not approved" in text.lower()
                or "yellow" in text.lower()
                or "missing" in text.lower()
            ):
                confidence = "low"

            findings.append(
                {
                    "theme": doc["source_type"],
                    "finding": text,
                    "confidence": confidence,
                    "citations": [
                        {
                            "source": doc["source_file"],
                            "stable_source_id": doc["stable_source_id"],
                            "source_type": doc["source_type"],
                            "quote_or_fact": text[:140],
                        }
                    ],
                    "conflict_or_ambiguity": (
                        "Needs human review" if confidence == "low" else None
                    ),
                }
            )

        return {
            "findings": findings,
            "evidence": docs,
            "llm_used": False,
        }
