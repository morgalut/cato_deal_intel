from __future__ import annotations

from app.contracts.approval import ApprovalRouteResult, ApprovalType
from app.observability.logging import get_logger, log_stage
from pydantic import BaseModel, Field

logger = get_logger("tools.approval")


class ApprovalDecisionInput(BaseModel):
    recommendation_id: str = Field(min_length=1)
    action_text: str = Field(min_length=1)
    confidence: str = Field(min_length=1)
    requested_discount: float | None = None
    contains_legal_terms: bool = False
    contains_customer_facing_concession_language: bool = False
    has_conflicting_evidence: bool = False


class ApprovalRouterTool:
    name: str = "approval_router"
    description: str = (
        "Routes high-impact recommendations to human approval. "
        "This tool is deterministic and must run after LLM recommendation generation."
    )

    def run(
        self,
        request: ApprovalDecisionInput,
    ) -> ApprovalRouteResult:
        with log_stage(
            logger,
            "tool.approval_router",
            recommendation_id=request.recommendation_id,
            confidence=request.confidence,
        ):
            approval_types: list[ApprovalType] = []

            if request.requested_discount is not None:
                if request.requested_discount > 10:
                    approval_types.append("deal_desk")

                if request.requested_discount > 15:
                    approval_types.append("sales_leader")

            if request.contains_legal_terms:
                approval_types.append("legal")

            if request.contains_customer_facing_concession_language:
                approval_types.append("deal_desk")

            if request.has_conflicting_evidence or request.confidence == "low":
                approval_types.append("human_reviewer")

            unique_approval_types: list[ApprovalType] = sorted(set(approval_types))

            approval_required: bool = bool(unique_approval_types)

            result = ApprovalRouteResult(
                approval_required=approval_required,
                approval_types=unique_approval_types,
                approval_status=("pending_approval" if approval_required else "not_required"),
                customer_facing_allowed=not approval_required,
            )

            logger.info(
                "tool.approval_router.result",
                recommendation_id=request.recommendation_id,
                approval_required=result.approval_required,
                approval_types=result.approval_types,
                approval_status=result.approval_status,
                customer_facing_allowed=result.customer_facing_allowed,
            )

            return result
