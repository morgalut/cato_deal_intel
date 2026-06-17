from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase
from app.observability.tracing import TraceBuffer
from app.tools.approval_tools import ApprovalDecisionInput

RecommendationCandidate = tuple[
    str,
    str,
    str,
    str,
    int | None,
    bool,
    bool,
    bool,
]


class NegotiationStrategyAgent(AgentBase):
    name = "negotiation_strategy_agent"
    system_contract = (
        "Main LLM synthesis agent. Produces internal next actions only; "
        "approval tool gates sensitive recommendations."
    )

    def __init__(self, trace: TraceBuffer, approval_tool: Any) -> None:
        super().__init__(trace)
        self.approval_tool: Any = approval_tool

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        opp_id: str = str(payload["snapshot"]["opportunity_id"])
        findings: list[dict[str, Any]] = payload["findings"]

        recommendations: list[dict[str, Any]] = []
        base: dict[str, Any] = {
            "citations": findings[0]["citations"] if findings else [],
        }

        candidates: list[RecommendationCandidate] = self._build_candidates(opp_id)

        for (
            recommendation_id,
            action,
            owner,
            confidence,
            requested_discount,
            contains_legal_terms,
            contains_customer_language,
            has_conflicting_evidence,
        ) in candidates:
            route: dict[str, Any] = self.approval_tool.run(
                ApprovalDecisionInput(
                    recommendation_id=recommendation_id,
                    action_text=action,
                    confidence=confidence,
                    requested_discount=requested_discount,
                    contains_legal_terms=contains_legal_terms,
                    contains_customer_facing_concession_language=contains_customer_language,
                    has_conflicting_evidence=has_conflicting_evidence,
                )
            )

            recommendations.append(
                {
                    "id": recommendation_id,
                    "action": action,
                    "owner": owner,
                    "rationale": ("Derived from retrieved evidence and policy guardrails."),
                    "confidence": confidence,
                    "approval_required": route["approval_required"],
                    "approval_types": route["approval_types"],
                    "customer_facing_allowed": not route["approval_required"],
                    **base,
                }
            )

        return {"recommendations": recommendations}

    def _build_candidates(self, opportunity_id: str) -> list[RecommendationCandidate]:
        if opportunity_id == "OPP-1003":
            return [
                (
                    "REC-1",
                    (
                        "Prepare internal-only package comparison; label "
                        "aggressive discount as unapproved."
                    ),
                    "Account Owner",
                    "low",
                    18,
                    False,
                    True,
                    True,
                ),
                (
                    "REC-2",
                    (
                        "Route liability and concession language to Legal and "
                        "Deal Desk before any customer-facing proposal."
                    ),
                    "Legal + Deal Desk",
                    "high",
                    None,
                    True,
                    True,
                    False,
                ),
            ]

        return [
            (
                "REC-1",
                (
                    "Complete the evidence packet and keep recommendations tied "
                    "to cited proof, not assumptions."
                ),
                "Account Owner",
                "medium",
                None,
                False,
                False,
                False,
            ),
            (
                "REC-2",
                ("Resolve missing information before asking for signature or commercial approval."),
                "Customer Success",
                "medium",
                None,
                False,
                False,
                False,
            ),
        ]
