from __future__ import annotations

from app.schemas.api_models import HealthResponse
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
