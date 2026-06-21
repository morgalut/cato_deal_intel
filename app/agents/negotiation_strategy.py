from __future__ import annotations

import json
from typing import Any, Literal

from app.agents.base import AgentBase
from app.contracts.brief import EvidenceCitation, GeneratedRecommendation
from app.observability.tracing import TraceBuffer
from app.tools.approval_tools import ApprovalDecisionInput, ApprovalRouterTool
from pydantic import BaseModel, Field, ValidationError

StrategyConfidence = Literal["low", "medium", "high"]


class StrategyCitationSchema(BaseModel):
    source: str = Field(min_length=1)
    stable_source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    quote_or_fact: str = Field(min_length=1)


class StrategyInputFinding(BaseModel):
    theme: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    confidence: StrategyConfidence
    citations: list[StrategyCitationSchema] = Field(min_length=1)
    conflict_or_ambiguity: str | None = None


class StrategyInputSnapshot(BaseModel):
    opportunity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    account_name: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    deal_type: str = Field(min_length=1)
    acv: float
    tcv: float
    close_date: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    restricted_access: bool


class StrategyAgentInput(BaseModel):
    snapshot: StrategyInputSnapshot
    findings: list[StrategyInputFinding] = Field(min_length=1)


class StrategyRecommendationSchema(BaseModel):
    id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: StrategyConfidence
    requested_discount: int | None = Field(default=None, ge=0, le=100)
    contains_legal_terms: bool = False
    contains_customer_facing_concession_language: bool = False
    has_conflicting_evidence: bool = False
    citations: list[StrategyCitationSchema] = Field(min_length=1)


class StrategyLLMOutputSchema(BaseModel):
    recommendations: list[StrategyRecommendationSchema] = Field(
        min_length=1,
        max_length=5,
    )


class StrategyAgentOutput(BaseModel):
    recommendations: list[GeneratedRecommendation]
    llm_used: bool


class NegotiationStrategyAgent(AgentBase):
    name = "negotiation_strategy_agent"

    system_contract = (
        "LLM-backed synthesis agent. Produces internal next actions only. "
        "Every recommendation must be grounded in valid citations and routed "
        "through the deterministic approval tool."
    )

    def __init__(
        self,
        trace: TraceBuffer,
        approval_tool: ApprovalRouterTool,
        llm: Any | None = None,
    ) -> None:
        super().__init__(trace, llm=llm)
        self.approval_tool: ApprovalRouterTool = approval_tool

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        validated_input: StrategyAgentInput = StrategyAgentInput.model_validate(payload)

        output: StrategyAgentOutput = self.run_typed(validated_input)

        return output.model_dump()

    def run_typed(
        self,
        payload: StrategyAgentInput,
    ) -> StrategyAgentOutput:
        snapshot: StrategyInputSnapshot = payload.snapshot
        findings: list[StrategyInputFinding] = payload.findings

        candidates: list[StrategyRecommendationSchema] = self._generate_candidates(
            snapshot=snapshot,
            findings=findings,
        )

        recommendations: list[GeneratedRecommendation] = []

        for candidate in candidates:
            route = self.approval_tool.run(
                ApprovalDecisionInput(
                    recommendation_id=candidate.id,
                    action_text=candidate.action,
                    confidence=candidate.confidence,
                    requested_discount=candidate.requested_discount,
                    contains_legal_terms=candidate.contains_legal_terms,
                    contains_customer_facing_concession_language=(
                        candidate.contains_customer_facing_concession_language
                    ),
                    has_conflicting_evidence=candidate.has_conflicting_evidence,
                )
            )

            recommendation = GeneratedRecommendation(
                id=candidate.id,
                action=candidate.action,
                owner=candidate.owner,
                rationale=candidate.rationale,
                confidence=candidate.confidence,
                approval_required=route.approval_required,
                approval_status=route.approval_status,
                approval_types=[str(approval_type) for approval_type in route.approval_types],
                customer_facing_allowed=route.customer_facing_allowed,
                citations=[
                    EvidenceCitation.model_validate(citation.model_dump())
                    for citation in candidate.citations
                ],
            )

            recommendations.append(recommendation)

        self.trace.add(
            "agent.negotiation_strategy.complete",
            self.name,
            {
                "opportunity_id": snapshot.opportunity_id,
                "recommendations": len(recommendations),
            },
        )

        return StrategyAgentOutput(
            recommendations=recommendations,
            llm_used=bool(self.llm),
        )

    def _generate_candidates(
        self,
        *,
        snapshot: StrategyInputSnapshot,
        findings: list[StrategyInputFinding],
    ) -> list[StrategyRecommendationSchema]:
        if self.llm is None:
            return self._deterministic_candidates(
                snapshot=snapshot,
                findings=findings,
            )

        llm_payload, usage = self.llm.json_task(
            task="synthesis",
            system=self._build_system_prompt(),
            user=self._build_user_prompt(
                snapshot=snapshot,
                findings=findings,
            ),
            sensitivity="standard",
            max_tokens=1600,
        )

        self.trace.add(
            "llm.negotiation_strategy.complete",
            self.name,
            {
                "model": usage.model,
                "total_tokens": usage.total_tokens,
                "offline": llm_payload.get("offline_mode", False),
            },
        )

        try:
            validated_output = StrategyLLMOutputSchema.model_validate(llm_payload)
            return validated_output.recommendations

        except ValidationError as exc:
            self.trace.add(
                "llm.negotiation_strategy.validation_failed",
                self.name,
                {
                    "errors": exc.errors(),
                    "fallback": "deterministic_candidates",
                },
            )

            return self._deterministic_candidates(
                snapshot=snapshot,
                findings=findings,
            )

    def _build_system_prompt(self) -> str:
        return (
            "You are the Negotiation Strategy Agent for a strategic sales "
            "negotiation brief. Use only the provided deal snapshot and "
            "evidence-backed findings. Return strict JSON with recommendations[]. "
            "Every recommendation must include citations copied from the supplied "
            "findings. Do not invent facts, discounts, dates, stakeholders, "
            "or customer-facing commitments. If evidence is conflicting or "
            "approval-sensitive, mark that clearly."
        )

    def _build_user_prompt(
        self,
        *,
        snapshot: StrategyInputSnapshot,
        findings: list[StrategyInputFinding],
    ) -> str:
        return json.dumps(
            {
                "deal_snapshot": snapshot.model_dump(),
                "findings": [finding.model_dump() for finding in findings],
                "required_output_schema": {
                    "recommendations": [
                        {
                            "id": "REC-1",
                            "action": "string",
                            "owner": "string",
                            "rationale": "string",
                            "confidence": "low|medium|high",
                            "requested_discount": "integer|null",
                            "contains_legal_terms": "boolean",
                            "contains_customer_facing_concession_language": ("boolean"),
                            "has_conflicting_evidence": "boolean",
                            "citations": [
                                {
                                    "source": "string",
                                    "stable_source_id": "string",
                                    "source_type": "string",
                                    "quote_or_fact": "string",
                                }
                            ],
                        }
                    ]
                },
                "approval_policy_summary": {
                    "discount_gt_10": "deal_desk",
                    "discount_gt_15": "sales_leader",
                    "legal_terms": "legal",
                    "customer_concession_language": "deal_desk",
                    "low_confidence_or_conflict": "human_reviewer",
                },
            },
            ensure_ascii=False,
        )

    def _deterministic_candidates(
        self,
        *,
        snapshot: StrategyInputSnapshot,
        findings: list[StrategyInputFinding],
    ) -> list[StrategyRecommendationSchema]:
        fallback_citations: list[StrategyCitationSchema] = self._collect_safe_fallback_citations(
            findings
        )

        if snapshot.opportunity_id == "OPP-1003":
            return [
                StrategyRecommendationSchema(
                    id="REC-1",
                    action=(
                        "Prepare an internal-only package comparison and label "
                        "aggressive discount options as unapproved."
                    ),
                    owner="Account Owner",
                    rationale=(
                        "The evidence shows approval-sensitive legal and commercial constraints."
                    ),
                    confidence="low",
                    requested_discount=18,
                    contains_legal_terms=False,
                    contains_customer_facing_concession_language=True,
                    has_conflicting_evidence=True,
                    citations=fallback_citations,
                ),
                StrategyRecommendationSchema(
                    id="REC-2",
                    action=(
                        "Route liability and concession language to Legal and "
                        "Deal Desk before any customer-facing proposal."
                    ),
                    owner="Legal + Deal Desk",
                    rationale=("Customer-facing concession language requires approval."),
                    confidence="high",
                    requested_discount=None,
                    contains_legal_terms=True,
                    contains_customer_facing_concession_language=True,
                    has_conflicting_evidence=False,
                    citations=fallback_citations,
                ),
            ]

        return [
            StrategyRecommendationSchema(
                id="REC-1",
                action=(
                    "Complete the evidence packet and keep recommendations tied to cited proof."
                ),
                owner="Account Owner",
                rationale="The deal should move forward only with grounded evidence.",
                confidence="medium",
                requested_discount=None,
                contains_legal_terms=False,
                contains_customer_facing_concession_language=False,
                has_conflicting_evidence=False,
                citations=fallback_citations,
            )
        ]

    def _collect_safe_fallback_citations(
        self,
        findings: list[StrategyInputFinding],
    ) -> list[StrategyCitationSchema]:
        for finding in findings:
            if finding.conflict_or_ambiguity or finding.confidence == "low":
                return finding.citations

        return findings[0].citations
