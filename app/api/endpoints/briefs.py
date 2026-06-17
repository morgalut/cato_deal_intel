from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.container import get_brief_workflow
from app.schemas.api_models import BriefRequest
from app.security.permissions import PermissionDeniedError
from app.workflows.brief_workflow import BriefWorkflow

router = APIRouter(
    prefix="/briefs",
    tags=["briefs"],
)


@router.post("/generate")
def generate_brief(
    req: BriefRequest,
    workflow: Annotated[
        BriefWorkflow,
        Depends(get_brief_workflow),
    ],
) -> dict[str, Any]:
    try:
        return workflow.run(
            req.user_id,
            req.opportunity_id,
        )

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        ) from exc