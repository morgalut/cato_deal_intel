from __future__ import annotations

from typing import Annotated

from app.contracts.approval import (
    ApprovalDecision,
    ApprovalRequestRecord,
)
from app.dependencies.container import get_approval_repository
from app.repositories.approval_repository import ApprovalRepository
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
)


@router.get(
    "/pending",
    response_model=list[ApprovalRequestRecord],
)
def list_pending_approvals(
    repository: Annotated[
        ApprovalRepository,
        Depends(get_approval_repository),
    ],
    opportunity_id: str | None = None,
) -> list[ApprovalRequestRecord]:
    return repository.list_pending(
        opportunity_id=opportunity_id,
    )


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalRequestRecord,
)
def approve_request(
    approval_id: str,
    reviewer_id: str,
    repository: Annotated[
        ApprovalRepository,
        Depends(get_approval_repository),
    ],
    reason: str | None = None,
) -> ApprovalRequestRecord:
    result: ApprovalRequestRecord | None = repository.decide(
        ApprovalDecision(
            approval_id=approval_id,
            reviewer_id=reviewer_id,
            status="approved",
            reason=reason,
        )
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found.",
        )

    return result


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalRequestRecord,
)
def reject_request(
    approval_id: str,
    reviewer_id: str,
    repository: Annotated[
        ApprovalRepository,
        Depends(get_approval_repository),
    ],
    reason: str | None = None,
) -> ApprovalRequestRecord:
    result: ApprovalRequestRecord | None = repository.decide(
        ApprovalDecision(
            approval_id=approval_id,
            reviewer_id=reviewer_id,
            status="rejected",
            reason=reason,
        )
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found.",
        )

    return result
