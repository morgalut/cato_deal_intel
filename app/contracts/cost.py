from __future__ import annotations

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    model_name: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)


class CostSnapshot(BaseModel):
    total_cost_usd: float = Field(ge=0.0)
    budget_limit_usd: float = Field(ge=0.0)
    budget_remaining_usd: float
    budget_breached: bool
    calls: list[TokenUsage]