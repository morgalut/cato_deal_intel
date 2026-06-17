from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger, log_stage
from pydantic import BaseModel

logger = get_logger("tools.approval")


class ApprovalDecisionInput(BaseModel):
    recommendation_id: str
    action_text: str
    confidence: str
    requested_discount: float | None = None
    contains_legal_terms: bool = False
    contains_customer_facing_concession_language: bool = False
    has_conflicting_evidence: bool = False


class ApprovalRouterTool:
    name: str = "route_human_approval"
    description: str = (
        "Applies Deal Desk approval policy before sensitive recommendations can be used."
    )

    def run(self, inp: ApprovalDecisionInput) -> dict[str, Any]:
        with log_stage(
            logger,
            "tool.route_human_approval",
            recommendation_id=inp.recommendation_id,
            confidence=inp.confidence,
        ):
            approvals: list[str] = []
            if inp.requested_discount is not None and inp.requested_discount > 10:
                approvals.append("deal_desk")
            if inp.requested_discount is not None and inp.requested_discount > 15:
                approvals.append("sales_leader")
            if inp.contains_legal_terms:
                approvals.append("legal")
            if inp.contains_customer_facing_concession_language:
                approvals.append("deal_desk")
            if inp.confidence == "low" or inp.has_conflicting_evidence:
                approvals.append("human_reviewer")
            unique: list[str] = sorted(set(approvals))
            return {
                "recommendation_id": inp.recommendation_id,
                "approval_required": bool(unique),
                "approval_types": unique,
                "status": "pending" if unique else "approved_for_internal_use",
            }
