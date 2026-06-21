from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.observability.langsmith_tracing import traced
from app.observability.logging import get_logger, log_stage
from app.services.cost_manager import CostManager
from openai import OpenAI

logger = get_logger("llm")

JSON_FALLBACK_NOTE = "LLM returned invalid JSON; deterministic fallback used."
NON_OBJECT_JSON_NOTE = "LLM returned non-object JSON; deterministic fallback used."
DISABLED_NOTE = "LLM disabled; deterministic fallback used."
CLIENT_UNAVAILABLE_NOTE = "LLM client unavailable; deterministic fallback used."


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = "offline-deterministic"
    estimated_cost_usd: float = 0.0


class LLMClient:
    """Centralized production LLM gateway.

    Responsibilities:
    - model routing;
    - LangSmith tracing through the shared tracing plugin;
    - structured JSON generation;
    - safe JSON parsing;
    - deterministic fallback behavior;
    - token usage logging.
    """

    def __init__(
        self,
        default_model: str | None = None,
        cheap_model: str | None = None,
        cost_manager: CostManager | None = None,
    ) -> None:
        self.default_model: str = default_model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"

        self.cheap_model: str = cheap_model or os.getenv("OPENAI_CHEAP_MODEL") or "gpt-4.1-nano"

        self.cost_manager: CostManager = cost_manager or CostManager()

        self.enabled: bool = (
            bool(os.getenv("OPENAI_API_KEY")) and os.getenv("LLM_MODE", "live") != "offline"
        )

        self.client: OpenAI | None = OpenAI() if self.enabled else None

    def choose_model(
        self,
        task: str,
        sensitivity: str = "standard",
    ) -> str:
        cheap_tasks: set[str] = {
            "classification",
            "extraction",
            "citation_check",
        }

        if task in cheap_tasks and sensitivity == "standard":
            return self.cheap_model

        return self.default_model

    @traced(
        name="LLM.OpenAI.JsonTask",
        run_type="llm",
    )
    def _call_openai(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> Any:
        if self.client is None:
            raise RuntimeError("OpenAI client is not initialized.")

        return self.client.chat.completions.create(
            model=model,
            temperature=0.1,
            max_tokens=max_tokens,
            response_format={
                "type": "json_object",
            },
            messages=[
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": user,
                },
            ],
        )

    def _fallback_payload(
        self,
        *,
        task: str,
        note: str,
    ) -> dict[str, Any]:
        return {
            "offline_mode": True,
            "task": task,
            "note": note,
        }

    def _parse_json_response(
        self,
        *,
        content: str,
        task: str,
        model: str,
    ) -> dict[str, Any]:
        try:
            parsed = json.loads(content)

        except json.JSONDecodeError as exc:
            logger.exception(
                "llm.invalid_json",
                task=task,
                model=model,
                error=str(exc),
                content_preview=content[:1000],
                content_length=len(content),
            )

            return self._fallback_payload(
                task=task,
                note=JSON_FALLBACK_NOTE,
            )

        if isinstance(parsed, dict):
            return parsed

        logger.info(
            "llm.invalid_json_type",
            task=task,
            model=model,
            response_type=type(parsed).__name__,
        )

        return self._fallback_payload(
            task=task,
            note=NON_OBJECT_JSON_NOTE,
        )

    def json_task(
        self,
        *,
        task: str,
        system: str,
        user: str,
        sensitivity: str = "standard",
        max_tokens: int = 1200,
    ) -> tuple[dict[str, Any], LLMUsage]:
        model: str = self.choose_model(
            task,
            sensitivity,
        )

        prompt_chars: int = len(system) + len(user)

        with log_stage(
            logger,
            "llm.call",
            task=task,
            model=model,
            sensitivity=sensitivity,
            prompt_chars=prompt_chars,
            max_tokens=max_tokens,
        ):
            if not self.enabled:
                return (
                    self._fallback_payload(
                        task=task,
                        note=DISABLED_NOTE,
                    ),
                    LLMUsage(model="offline-deterministic"),
                )

            if self.client is None:
                return (
                    self._fallback_payload(
                        task=task,
                        note=CLIENT_UNAVAILABLE_NOTE,
                    ),
                    LLMUsage(model="offline-deterministic"),
                )

            self.cost_manager.assert_preflight_budget(
                model_name=model,
                prompt_text=f"{system}\n{user}",
                max_completion_tokens=max_tokens,
            )

            try:
                response = self._call_openai(
                    model=model,
                    system=system,
                    user=user,
                    max_tokens=max_tokens,
                )

            except Exception:
                logger.exception(
                    "llm.call.failed",
                    task=task,
                    model=model,
                )
                raise

            choice = response.choices[0]
            content: str = choice.message.content or "{}"
            finish_reason: str | None = getattr(choice, "finish_reason", None)

            usage = LLMUsage(
                prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
                model=model,
            )

            tracked_usage = self.cost_manager.track_usage(
                model_name=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )

            usage.estimated_cost_usd = tracked_usage.estimated_cost_usd

            logger.info(
                "llm.usage",
                task=task,
                model=model,
                finish_reason=finish_reason,
                response_chars=len(content),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
            )

            if finish_reason == "length":
                logger.info(
                    "llm.response_truncated",
                    task=task,
                    model=model,
                    max_tokens=max_tokens,
                    response_chars=len(content),
                )

            return (
                self._parse_json_response(
                    content=content,
                    task=task,
                    model=model,
                ),
                usage,
            )
