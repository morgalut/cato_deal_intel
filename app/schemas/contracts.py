from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]


class Citation(BaseModel):
    source: str
    stable_source_id: str
    source_type: str
    quote_or_fact: str


class EvidenceItem(BaseModel):
    stable_source_id: str
    source_file: str
    source_type: str
    opportunity_id: str | None = None
    account_id: str | None = None
    source_access_level: str = "standard"
    content: str
    score: float = 0.0


class DealSnapshot(BaseModel):
    opportunity_id: str
    account_id: str
    account_name: str
    stage: str
    deal_type: str
    acv: float
    tcv: float
    close_date: str
    owner: str
    risk_level: str
    restricted_access: bool
    citations: list[Citation] = Field(default_factory=list)


class ConversationFinding(BaseModel):
    theme: str
    finding: str
    confidence: Confidence
    citations: list[Citation]
    conflict_or_ambiguity: str | None = None


class Stakeholder(BaseModel):
    name: str
    title: str
    role_in_deal: str
    influence_level: str
    sentiment: str
    notes: str
    citations: list[Citation] = Field(default_factory=list)


class Recommendation(BaseModel):
    id: str
    action: str
    owner: str
    rationale: str
    confidence: Confidence
    approval_required: bool = False
    approval_types: list[str] = Field(default_factory=list)
    customer_facing_allowed: bool = False
    citations: list[Citation] = Field(default_factory=list)


class StrategicDealBrief(BaseModel):
    deal_snapshot: DealSnapshot
    executive_summary: str
    buyer_goals_and_business_drivers: list[ConversationFinding]
    stakeholder_map: list[Stakeholder]
    negotiation_state: list[ConversationFinding]
    recommended_next_actions: list[Recommendation]
    missing_information: list[str]
    source_evidence: list[EvidenceItem]
    confidence_and_review_warnings: list[str]
