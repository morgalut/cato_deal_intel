from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://deal:deal@localhost:5432/deal_intel",
    )

    # OpenAI
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    # LangSmith / LangChain tracing
    LANGSMITH_TRACING: bool = _get_bool("LANGSMITH_TRACING", True)
    langchain_endpoint: str = os.getenv(
        "LANGCHAIN_ENDPOINT",
        "https://api.smith.langchain.com",
    )
    langchain_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langchain_project: str = os.getenv(
        "LANGCHAIN_PROJECT",
        "cato-deal-intelligence",
    )

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
