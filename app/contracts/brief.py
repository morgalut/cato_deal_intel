from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ConfidenceLevel = Literal["low", "medium", "high"]

GeneratedApprovalStatus = Literal[
    "not_required",
    "pending_approval",
]

StoredApprovalStatus = Literal[
    "not_required",
    "pending_approval",
    "approved",
    "rejected",
]

CITATION_FIELDS_EMPTY = "citation_fields_empty"
APPROVAL_REQUIRED_MUST_BE_PENDING = "approval_required_must_be_pending"
APPROVAL_NOT_REQUIRED_STATUS_INVALID = "approval_not_required_status_invalid"
PENDING_APPROVAL_BLOCKS_CUSTOMER_OUTPUT = "pending_approval_blocks_customer_output"


class ContractValidationError(ValueError):
    """Raised when a typed contract receives invalid or unsafe data."""

    def __init__(
        self,
        code: str,
        *,
        field_name: str | None = None,
    ) -> None:
        self.code: str = code
        self.field_name: str | None = field_name

        message = code
        if field_name is not None:
            message = f"{code}:{field_name}"

        super().__init__(message)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class BriefMetadata(StrictBaseModel):
    brief_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    created_at: str


class EvidenceCitation(StrictBaseModel):
    source: str = Field(min_length=1)
    stable_source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    quote_or_fact: str = Field(min_length=1)

    @field_validator(
        "source",
        "stable_source_id",
        "source_type",
        "quote_or_fact",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ContractValidationError(CITATION_FIELDS_EMPTY)

        return cleaned


class DocumentEvidence(StrictBaseModel):
    source_file: str = Field(min_length=1)
    stable_source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_access_level: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DealSnapshot(StrictBaseModel):
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
    citations: list[EvidenceCitation] = Field(min_length=1)


class AgentFinding(StrictBaseModel):
    theme: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    confidence: ConfidenceLevel
    citations: list[EvidenceCitation] = Field(min_length=1)
    conflict_or_ambiguity: str | None = None


class Stakeholder(StrictBaseModel):
    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    role_in_deal: str = Field(min_length=1)
    influence_level: str = Field(min_length=1)
    sentiment: str = Field(min_length=1)
    notes: str | None = None
    citations: list[EvidenceCitation] = Field(min_length=1)


class BaseRecommendation(StrictBaseModel):
    id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: ConfidenceLevel
    approval_required: bool
    approval_types: list[str] = Field(default_factory=list)
    customer_facing_allowed: bool
    citations: list[EvidenceCitation] = Field(min_length=1)


class GeneratedRecommendation(BaseRecommendation):
    approval_status: GeneratedApprovalStatus

    @model_validator(mode="after")
    def validate_generated_approval_state(self) -> GeneratedRecommendation:
        if self.approval_required and self.approval_status != "pending_approval":
            raise ContractValidationError(APPROVAL_REQUIRED_MUST_BE_PENDING)

        if not self.approval_required and self.approval_status != "not_required":
            raise ContractValidationError(APPROVAL_NOT_REQUIRED_STATUS_INVALID)

        if self.approval_required and self.customer_facing_allowed:
            raise ContractValidationError(PENDING_APPROVAL_BLOCKS_CUSTOMER_OUTPUT)

        return self


class Recommendation(BaseRecommendation):
    approval_status: StoredApprovalStatus


class TraceEvent(StrictBaseModel):
    ts: float
    run_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    payload: dict[str, Any]


class StrategicDealBrief(StrictBaseModel):
    deal_snapshot: DealSnapshot
    executive_summary: str = Field(min_length=1)
    buyer_goals_and_business_drivers: list[AgentFinding]
    stakeholder_map: list[Stakeholder]
    negotiation_state: list[AgentFinding]
    recommended_next_actions: list[Recommendation]
    missing_information: list[str]
    source_evidence: list[DocumentEvidence]
    confidence_and_review_warnings: list[str]
    llm_usage_mode: str = Field(min_length=1)
    trace: list[TraceEvent]
