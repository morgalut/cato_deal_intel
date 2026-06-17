from __future__ import annotations

from typing import Any

from app.agents.conversation_intel import ConversationIntelligenceAgent
from app.agents.deal_context import DealContextAgent
from app.agents.negotiation_strategy import NegotiationStrategyAgent
from app.agents.stakeholder import StakeholderMapAgent
from app.observability.logging import get_logger, log_stage
from app.observability.tracing import TraceBuffer
from app.rag.hybrid import LocalHybridRetriever
from app.rag.loader import EvidenceLoader
from app.security.permissions import PermissionService
from app.services.llm import LLMClient
from app.tools.approval_tools import ApprovalRouterTool
from app.tools.retrieval_tools import RetrieveEvidenceTool

logger = get_logger("workflow.brief")

EXECUTIVE_SUMMARY = "Grounded negotiation-preparation brief generated from allowed evidence only."

APPROVAL_WARNING = "Some recommendations are internal-only until human approval is completed."

LOW_CONFIDENCE_WARNING = "Conflicting or low-confidence evidence detected; route to reviewer."

LLM_USAGE_MODE = "live_model_after_permission_filtered_retrieval"


class BriefWorkflow:
    """Orchestrates the full brief-generation graph."""

    def __init__(
        self,
        data_dir: str = "data",
        llm: LLMClient | None = None,
    ) -> None:
        self.data_dir: str = data_dir
        self.llm: LLMClient = llm or LLMClient()

        with log_stage(
            logger,
            "workflow.init",
            data_dir=data_dir,
        ):
            self.permissions: PermissionService = PermissionService(data_dir)

            docs: list[dict[str, Any]] = EvidenceLoader(
                data_dir,
            ).load_documents()

            self.retriever: LocalHybridRetriever = LocalHybridRetriever(
                docs,
                self.permissions,
            )

    def run(
        self,
        user_id: str,
        opportunity_id: str,
    ) -> dict[str, Any]:
        trace = TraceBuffer()

        trace.add(
            "workflow.start",
            "brief_workflow",
            {
                "user_id": user_id,
                "opportunity_id": opportunity_id,
            },
        )

        with log_stage(
            logger,
            "workflow.run",
            user_id=user_id,
            opportunity_id=opportunity_id,
            run_id=trace.run_id,
        ):
            with log_stage(
                logger,
                "permission.authorize_opportunity",
                user_id=user_id,
                opportunity_id=opportunity_id,
            ):
                self.permissions.authorize_opportunity(
                    user_id,
                    opportunity_id,
                )

            retrieval_tool = RetrieveEvidenceTool(self.retriever)
            approval_tool = ApprovalRouterTool()

            context: dict[str, Any] = DealContextAgent(
                trace,
                self.data_dir,
            ).invoke(
                {
                    "opportunity_id": opportunity_id,
                }
            )

            conv: dict[str, Any] = ConversationIntelligenceAgent(
                trace,
                retrieval_tool,
                llm=self.llm,
            ).invoke(
                {
                    "user_id": user_id,
                    "opportunity_id": opportunity_id,
                }
            )

            stakeholders: dict[str, Any] = StakeholderMapAgent(
                trace,
                self.data_dir,
            ).invoke(
                {
                    "opportunity_id": opportunity_id,
                }
            )

            strategy: dict[str, Any] = NegotiationStrategyAgent(
                trace,
                approval_tool,
            ).invoke(
                {
                    "snapshot": context["snapshot"],
                    "findings": conv["findings"],
                }
            )

            warnings: list[str] = self._build_warnings(
                recommendations=strategy["recommendations"],
                findings=conv["findings"],
            )

            brief: dict[str, Any] = {
                "deal_snapshot": context["snapshot"],
                "executive_summary": EXECUTIVE_SUMMARY,
                "buyer_goals_and_business_drivers": conv["findings"][:3],
                "stakeholder_map": stakeholders["stakeholders"],
                "negotiation_state": conv["findings"][3:],
                "recommended_next_actions": strategy["recommendations"],
                "missing_information": [
                    "Confirm all open approval states",
                    (
                        "Validate unresolved technical or legal items "
                        "before customer-facing language"
                    ),
                ],
                "source_evidence": conv["evidence"],
                "confidence_and_review_warnings": warnings,
                "llm_usage_mode": LLM_USAGE_MODE,
                "trace": trace.events,
            }

            trace.add(
                "workflow.complete",
                "brief_workflow",
                {
                    "recommendations": len(strategy["recommendations"]),
                    "evidence": len(conv["evidence"]),
                },
            )

            logger.info(
                "workflow.brief.complete",
                run_id=trace.run_id,
                opportunity_id=opportunity_id,
                evidence_count=len(conv["evidence"]),
                recommendation_count=len(strategy["recommendations"]),
            )

            return brief

    def _build_warnings(
        self,
        recommendations: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> list[str]:
        warnings: list[str] = []

        if any(bool(item["approval_required"]) for item in recommendations):
            warnings.append(APPROVAL_WARNING)

        if any(bool(item.get("conflict_or_ambiguity")) for item in findings):
            warnings.append(LOW_CONFIDENCE_WARNING)

        return warnings
