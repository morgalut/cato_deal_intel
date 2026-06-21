from __future__ import annotations

from typing import Literal

from app.contracts.brief import (
    ContractValidationError,
    EvidenceCitation,
    StrictBaseModel,
)
from datetime import datetime
from pydantic import Field, model_validator

ApprovalType = Literal[
    "deal_desk",
    "sales_leader",
    "legal",
    "human_reviewer",
]

ApprovalStatus = Literal[
    "pending_approval",
    "approved",
    "rejected",
]

APPROVAL_REQUEST_WITHOUT_TYPES = "approval_request_without_types"
CUSTOMER_OUTPUT_WITH_PENDING_APPROVAL = "customer_output_with_pending_approval"


    
class ApprovalRequest(StrictBaseModel):
    recommendation_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    action_text: str = Field(min_length=1)
    approval_types: list[ApprovalType] = Field(min_length=1)
    status: ApprovalStatus = "pending_approval"
    requested_by: str = Field(min_length=1)
    citations: list[EvidenceCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_approval_request(self) -> ApprovalRequest:
        if self.status == "pending_approval" and not self.approval_types:
            raise ContractValidationError(
                APPROVAL_REQUEST_WITHOUT_TYPES,
                field_name="approval_types",
            )

        return self

class ApprovalRequestRecord(ApprovalRequest):
    approval_id: str
    reviewer_id: str | None = None
    decision_reason: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None
    
class ApprovalDecision(StrictBaseModel):
    approval_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    status: ApprovalStatus
    reason: str | None = None


class ApprovalRouteResult(StrictBaseModel):
    approval_required: bool
    approval_types: list[ApprovalType] = Field(default_factory=list)
    approval_status: Literal["not_required", "pending_approval"]
    customer_facing_allowed: bool

    @model_validator(mode="after")
    def validate_route(self) -> ApprovalRouteResult:
        if self.approval_required and self.approval_status != "pending_approval":
            raise ContractValidationError(
                "approval_required_invalid_status",
                field_name="approval_status",
            )

        if self.approval_required and self.customer_facing_allowed:
            raise ContractValidationError(
                CUSTOMER_OUTPUT_WITH_PENDING_APPROVAL,
                field_name="customer_facing_allowed",
            )

        return self
