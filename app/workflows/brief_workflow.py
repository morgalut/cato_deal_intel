from __future__ import annotations

from typing import Any, cast

from app.agents.conversation_intel import ConversationIntelligenceAgent
from app.agents.negotiation_strategy import NegotiationStrategyAgent
from app.contracts.approval import ApprovalRequest, ApprovalType
from app.contracts.brief import (
    AgentFinding,
    DealSnapshot,
    DocumentEvidence,
    EvidenceCitation,
    Recommendation,
    StrategicDealBrief,
    TraceEvent,
)
from app.observability.logging import get_logger, log_stage
from app.observability.tracing import TraceBuffer
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.brief_repository import BriefRepository
from app.repositories.trace_repository import TraceRepository
from app.security.permissions import PermissionService
from app.services.llm import LLMClient
from app.tools.approval_tools import ApprovalRouterTool
from app.tools.retrieval_tools import (
    RetrieveEvidenceTool,
    RetrieverProtocol,
)

logger = get_logger("workflow.brief")

EXECUTIVE_SUMMARY = "Grounded negotiation-preparation brief generated from allowed evidence only."
APPROVAL_WARNING = "Some recommendations are internal-only until human approval is completed."
LOW_CONFIDENCE_WARNING = "Conflicting or low-confidence evidence detected; route to reviewer."
LLM_USAGE_MODE = "live_model_after_permission_filtered_retrieval"


class BriefWorkflow:
    """Production orchestration for Strategic Deal Intelligence Briefs."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        permissions: PermissionService,
        retriever: RetrieverProtocol,
        approval_repository: ApprovalRepository,
        trace_repository: TraceRepository,
        brief_repository: BriefRepository,
    ) -> None:
        self.llm: LLMClient = llm
        self.permissions: PermissionService = permissions
        self.retriever: RetrieverProtocol = retriever
        self.approval_repository: ApprovalRepository = approval_repository
        self.trace_repository: TraceRepository = trace_repository
        self.brief_repository: BriefRepository = brief_repository

    def run(
        self,
        user_id: str,
        opportunity_id: str,
    ) -> dict[str, Any]:
        trace = TraceBuffer()
        self.llm.cost_manager.start_run()

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
            auth_context: dict[str, Any] = self.permissions.authorize_opportunity(
                user_id,
                opportunity_id,
            )

            profile: dict[str, Any] = auth_context["profile"]
            opportunity: dict[str, Any] = auth_context["opportunity"]

            retrieval_tool = RetrieveEvidenceTool(self.retriever)
            approval_tool = ApprovalRouterTool()

            snapshot: DealSnapshot = self._build_deal_snapshot(opportunity)

            conversation: dict[str, Any] = ConversationIntelligenceAgent(
                trace,
                retrieval_tool,
                llm=self.llm,
            ).invoke(
                {
                    "user_id": user_id,
                    "opportunity_id": opportunity_id,
                }
            )

            evidence_rows: list[dict[str, Any]] = list(conversation.get("evidence", []))
            raw_findings: list[dict[str, Any]] = list(conversation.get("findings", []))

            findings: list[AgentFinding] = [
                AgentFinding.model_validate(
                    self._normalize_finding_citations(
                        finding=finding,
                        source_evidence=evidence_rows,
                    )
                )
                for finding in raw_findings
            ]

            if not findings:
                findings = [
                    AgentFinding(
                        theme="missing_evidence",
                        finding=(
                            "No relevant evidence was retrieved for this opportunity. "
                            "A human reviewer should verify ingestion and source coverage."
                        ),
                        confidence="low",
                        citations=[
                            EvidenceCitation(
                                source="database:documents",
                                stable_source_id=opportunity_id,
                                source_type="system",
                                quote_or_fact="No relevant evidence retrieved.",
                            )
                        ],
                        conflict_or_ambiguity="Evidence retrieval returned no findings.",
                    )
                ]

            strategy: dict[str, Any] = NegotiationStrategyAgent(
                trace,
                approval_tool,
                llm=self.llm,
            ).invoke(
                {
                    "snapshot": snapshot.model_dump(),
                    "findings": [finding.model_dump() for finding in findings],
                }
            )

            recommendations: list[Recommendation] = [
                Recommendation.model_validate(recommendation)
                for recommendation in strategy["recommendations"]
            ]

            self._persist_pending_approvals(
                user_id=user_id,
                opportunity_id=opportunity_id,
                recommendations=recommendations,
            )

            source_evidence: list[DocumentEvidence] = self._build_source_evidence(
                opportunity=opportunity,
                retrieved_evidence=evidence_rows,
            )

            warnings: list[str] = self._build_warnings(
                recommendations=recommendations,
                findings=findings,
            )

            cost_snapshot = self.llm.cost_manager.snapshot()

            trace.add(
                "workflow.cost_metrics",
                "budget_enforcement",
                cost_snapshot.model_dump(),
            )

            trace.add(
                "workflow.complete",
                "brief_workflow",
                {
                    "recommendations": len(recommendations),
                    "evidence": len(source_evidence),
                    "total_cost_usd": cost_snapshot.total_cost_usd,
                    "budget_limit_usd": cost_snapshot.budget_limit_usd,
                    "budget_breached": cost_snapshot.budget_breached,
                },
            )

            trace_events: list[TraceEvent] = [
                TraceEvent.model_validate(event) for event in trace.events
            ]

            brief = StrategicDealBrief(
                deal_snapshot=snapshot,
                executive_summary=EXECUTIVE_SUMMARY,
                buyer_goals_and_business_drivers=findings[:3],
                stakeholder_map=[],
                negotiation_state=findings[3:],
                recommended_next_actions=recommendations,
                missing_information=[
                    "Confirm all open approval states",
                    (
                        "Validate unresolved technical or legal items "
                        "before customer-facing language"
                    ),
                    (
                        "Populate stakeholder map from DB-backed contact "
                        "repository in the next production increment"
                    ),
                ],
                source_evidence=source_evidence,
                confidence_and_review_warnings=warnings,
                llm_usage_mode=LLM_USAGE_MODE,
                trace=trace_events,
            )

            safe_brief: StrategicDealBrief = self.permissions.validate_and_sanitize_response(
                profile,
                brief,
            )

            self.trace_repository.save_batch(
                events=safe_brief.trace,
            )

            brief_metadata = self.brief_repository.save_brief(
                run_id=trace.run_id,
                user_id=user_id,
                opportunity_id=opportunity_id,
                brief=safe_brief,
            )

            logger.info(
                "workflow.brief.complete",
                run_id=trace.run_id,
                opportunity_id=opportunity_id,
                evidence_count=len(source_evidence),
                recommendation_count=len(recommendations),
            )

            metadata: dict[str, Any] = (
                brief_metadata.model_dump()
                if hasattr(brief_metadata, "model_dump")
                else dict(brief_metadata)
            )
            metadata["cost"] = cost_snapshot.model_dump()

            return {
                "brief": safe_brief.model_dump(),
                "metadata": metadata,
            }

    def _normalize_finding_citations(
        self,
        *,
        finding: dict[str, Any],
        source_evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_finding: dict[str, Any] = dict(finding)
        raw_citations = normalized_finding.get("citations", [])

        if not isinstance(raw_citations, list):
            normalized_finding["citations"] = []
            return normalized_finding

        evidence_by_id: dict[str, dict[str, Any]] = {
            str(row["stable_source_id"]): row for row in source_evidence
        }

        normalized_citations: list[dict[str, Any]] = []

        for citation in raw_citations:
            if isinstance(citation, dict):
                normalized_citations.append(citation)
                continue

            evidence = evidence_by_id.get(str(citation))
            if evidence is None:
                continue

            normalized_citations.append(
                {
                    "source": str(evidence["source_file"]),
                    "stable_source_id": str(evidence["stable_source_id"]),
                    "source_type": str(evidence["source_type"]),
                    "quote_or_fact": str(evidence["content"])[:140],
                }
            )

        normalized_finding["citations"] = normalized_citations
        return normalized_finding

    def _to_approval_types(
        self,
        values: list[str],
    ) -> list[ApprovalType]:
        allowed: set[str] = {
            "deal_desk",
            "sales_leader",
            "legal",
            "human_reviewer",
        }

        result: list[ApprovalType] = []

        for value in values:
            if value in allowed:
                result.append(cast(ApprovalType, value))

        return result

    def _build_deal_snapshot(
        self,
        opportunity: dict[str, Any],
    ) -> DealSnapshot:
        opportunity_id = str(opportunity["opportunity_id"])

        return DealSnapshot(
            opportunity_id=opportunity_id,
            account_id=str(opportunity["account_id"]),
            account_name=str(opportunity["account_name"]),
            stage=str(opportunity["stage"]),
            deal_type=str(opportunity["type"]),
            acv=float(opportunity["acv"]),
            tcv=float(opportunity["tcv"]),
            close_date=str(opportunity["close_date"]),
            owner=str(opportunity["owner"]),
            risk_level=str(opportunity["risk_level"]),
            restricted_access=bool(opportunity["restricted_access"]),
            citations=[
                EvidenceCitation(
                    source="database:opportunities",
                    stable_source_id=opportunity_id,
                    source_type="salesforce",
                    quote_or_fact="CRM opportunity row",
                )
            ],
        )

    def _build_source_evidence(
        self,
        *,
        opportunity: dict[str, Any],
        retrieved_evidence: list[dict[str, Any]],
    ) -> list[DocumentEvidence]:
        evidence_items: list[DocumentEvidence] = [
            DocumentEvidence(
                source_file="database:opportunities",
                stable_source_id=str(opportunity["opportunity_id"]),
                source_type="salesforce",
                source_access_level="standard",
                content="CRM opportunity row",
                metadata={
                    "account_id": str(opportunity["account_id"]),
                    "stage": str(opportunity["stage"]),
                    "risk_level": str(opportunity["risk_level"]),
                },
            ),
            DocumentEvidence(
                source_file="synthetic_data/policies/deal_desk_policy.md",
                stable_source_id="DEAL-DESK-POLICY",
                source_type="policies",
                source_access_level="standard",
                content="Approval routing policy",
                metadata={},
            ),
        ]

        for row in retrieved_evidence:
            evidence_items.append(
                DocumentEvidence(
                    source_file=str(row["source_file"]),
                    stable_source_id=str(row["stable_source_id"]),
                    source_type=str(row["source_type"]),
                    source_access_level=str(row.get("source_access_level", "standard")),
                    content=str(row["content"]),
                    metadata=dict(row.get("metadata", {})),
                )
            )

        return evidence_items

    def _persist_pending_approvals(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        recommendations: list[Recommendation],
    ) -> None:
        for recommendation in recommendations:
            if recommendation.approval_status != "pending_approval":
                continue

            self.approval_repository.create_request(
                ApprovalRequest(
                    recommendation_id=recommendation.id,
                    opportunity_id=opportunity_id,
                    action_text=recommendation.action,
                    approval_types=self._to_approval_types(
                        recommendation.approval_types,
                    ),
                    status="pending_approval",
                    requested_by=user_id,
                    citations=recommendation.citations,
                )
            )

    def _build_warnings(
        self,
        recommendations: list[Recommendation],
        findings: list[AgentFinding],
    ) -> list[str]:
        warnings: list[str] = []

        if any(recommendation.approval_required for recommendation in recommendations):
            warnings.append(APPROVAL_WARNING)

        if any(finding.conflict_or_ambiguity for finding in findings):
            warnings.append(LOW_CONFIDENCE_WARNING)

        return warnings
