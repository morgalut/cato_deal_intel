from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.observability.logging import get_logger, log_stage
from openai import OpenAI

logger = get_logger("llm")


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = "offline-deterministic"


class LLMClient:
    """Cost-aware model wrapper.

    Use deterministic code for loading, permissions, routing and validation.
    Use the LLM only for synthesis/extraction where language judgment is useful.
    Keep prompts compact: pass top-k evidence snippets, not entire files.
    Force JSON output and validate downstream with Pydantic contracts.
    """

    def __init__(
        self,
        default_model: str | None = None,
        cheap_model: str | None = None,
    ) -> None:
        self.default_model: str = default_model or os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        )

        self.cheap_model: str = cheap_model or os.getenv(
            "OPENAI_CHEAP_MODEL",
            "gpt-4.1-nano",
        )

        self.enabled: bool = (
            bool(os.getenv("OPENAI_API_KEY")) and os.getenv("LLM_MODE", "live") != "offline"
        )

        self.client: OpenAI | None

        if self.enabled:
            self.client = OpenAI()
        else:
            self.client = None

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

    def json_task(
        self,
        *,
        task: str,
        system: str,
        user: str,
        sensitivity: str = "standard",
        max_tokens: int = 700,
    ) -> tuple[dict[str, Any], LLMUsage]:
        model = self.choose_model(task, sensitivity)
        with log_stage(
            logger,
            "llm.call",
            task=task,
            model=model,
            sensitivity=sensitivity,
            prompt_chars=len(system) + len(user),
        ):
            if not self.enabled:
                return {
                    "offline_mode": True,
                    "task": task,
                    "note": "LLM disabled; deterministic fallback used.",
                }, LLMUsage(model="offline-deterministic")
            resp = self.client.chat.completions.create(
                model=model,
                temperature=0.1,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            content = resp.choices[0].message.content or "{}"
            usage = LLMUsage(
                prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(resp.usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(resp.usage, "total_tokens", 0) or 0,
                model=model,
            )
            logger.info(
                "llm.usage",
                task=task,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            return json.loads(content), usage
