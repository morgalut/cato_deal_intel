from __future__ import annotations

from pydantic import BaseModel, Field


class BriefRequest(BaseModel):
    """Public API contract for generating a Strategic Deal Intelligence Brief."""

    opportunity_id: str = Field(..., examples=["OPP-1001"])
    user_id: str = Field(..., examples=["USR-5001"])


class IngestRequest(BaseModel):
    """Public API contract for loading deterministic evidence into the database."""

    data_dir: str = Field(default="data")
    truncate: bool = Field(default=True)


class HealthResponse(BaseModel):
    status: str
