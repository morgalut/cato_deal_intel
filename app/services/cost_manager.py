from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.contracts.cost import CostSnapshot, TokenUsage


class BudgetExceededError(RuntimeError):
    def __init__(
        self,
        *,
        limit_usd: float,
        current_usd: float,
    ) -> None:
        super().__init__(
            f"Token budget exceeded. Limit=${limit_usd:.6f}, current=${current_usd:.6f}",
        )
        self.limit_usd = limit_usd
        self.current_usd = current_usd


@dataclass
class _RunCostState:
    total_cost_usd: float = 0.0
    calls: list[TokenUsage] = field(default_factory=list)


_RUN_COST_STATE: ContextVar[_RunCostState] = ContextVar(
    "run_cost_state",
    default=_RunCostState(),
)


MODEL_PRICING_USD_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    # Conservative configurable defaults.
    # Override by editing here or loading from config in production.
    "gpt-4.1-mini": {
        "input": float(os.getenv("PRICE_GPT_4_1_MINI_INPUT_PER_1M", "0.40")),
        "output": float(os.getenv("PRICE_GPT_4_1_MINI_OUTPUT_PER_1M", "1.60")),
    },
    "gpt-4.1-nano": {
        "input": float(os.getenv("PRICE_GPT_4_1_NANO_INPUT_PER_1M", "0.10")),
        "output": float(os.getenv("PRICE_GPT_4_1_NANO_OUTPUT_PER_1M", "0.40")),
    },
}


class CostManager:
    """Per-run token and cost guardrail.

    Uses ContextVar so a singleton LLMClient can still track cost per request/run.
    """

    def __init__(
        self,
        max_run_budget_usd: float | None = None,
    ) -> None:
        self.max_run_budget_usd: float = max_run_budget_usd or float(
            os.getenv("MAX_RUN_BUDGET_USD", "0.05"),
        )

    def start_run(self) -> None:
        _RUN_COST_STATE.set(_RunCostState())

    def estimate_tokens(
        self,
        text: str,
    ) -> int:
        # Safe approximation without forcing tiktoken as a hard dependency.
        # Good enough for pre-flight budgeting. API usage remains source of truth.
        return max(1, len(text) // 4)

    def estimate_max_call_cost(
        self,
        *,
        model_name: str,
        prompt_tokens: int,
        max_completion_tokens: int,
    ) -> float:
        pricing = self._pricing_for(model_name)

        return (
            (prompt_tokens / 1_000_000) * pricing["input"]
            + (max_completion_tokens / 1_000_000) * pricing["output"]
        )

    def assert_preflight_budget(
        self,
        *,
        model_name: str,
        prompt_text: str,
        max_completion_tokens: int,
    ) -> None:
        state = _RUN_COST_STATE.get()
        estimated_prompt_tokens = self.estimate_tokens(prompt_text)

        estimated_cost = self.estimate_max_call_cost(
            model_name=model_name,
            prompt_tokens=estimated_prompt_tokens,
            max_completion_tokens=max_completion_tokens,
        )

        projected_cost = state.total_cost_usd + estimated_cost

        if projected_cost > self.max_run_budget_usd:
            raise BudgetExceededError(
                limit_usd=self.max_run_budget_usd,
                current_usd=projected_cost,
            )

    def track_usage(
        self,
        *,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> TokenUsage:
        state = _RUN_COST_STATE.get()
        pricing = self._pricing_for(model_name)

        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        call_cost = input_cost + output_cost

        usage = TokenUsage(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=call_cost,
        )

        state.total_cost_usd += call_cost
        state.calls.append(usage)

        if state.total_cost_usd > self.max_run_budget_usd:
            raise BudgetExceededError(
                limit_usd=self.max_run_budget_usd,
                current_usd=state.total_cost_usd,
            )

        return usage

    def snapshot(self) -> CostSnapshot:
        state = _RUN_COST_STATE.get()

        return CostSnapshot(
            total_cost_usd=state.total_cost_usd,
            budget_limit_usd=self.max_run_budget_usd,
            budget_remaining_usd=self.max_run_budget_usd - state.total_cost_usd,
            budget_breached=state.total_cost_usd > self.max_run_budget_usd,
            calls=state.calls,
        )

    def _pricing_for(
        self,
        model_name: str,
    ) -> dict[str, float]:
        return MODEL_PRICING_USD_PER_1M_TOKENS.get(
            model_name,
            {
                "input": 0.0,
                "output": 0.0,
            },
        )