from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Protocol


class EvidenceRepositoryProtocol(Protocol):
    def ingest_documents(
        self, documents: Iterable[dict[str, Any]], truncate: bool = False
    ) -> dict[str, Any]: ...

    def search_keyword(
        self,
        *,
        opportunity_id: str,
        account_id: str | None,
        allowed_source_types: list[str],
        allowed_access_levels: list[str],
        query: str,
        k: int = 10,
    ) -> list[dict[str, Any]]: ...


class UnitOfWork(ABC):
    """Future extension point for transaction-scoped repositories."""

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
