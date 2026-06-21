from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger, log_stage
from app.repositories.evidence_repository import EvidenceRepository
from app.security.permissions import PermissionService
from app.observability.langsmith_tracing import traced
logger = get_logger("rag.database_hybrid")


class DatabaseHybridRetriever:
    """DB-backed Hybrid RAG retriever.

    Security rule:
    permissions are resolved before SQL execution, and allowed metadata scopes
    are passed into the repository query. Restricted rows should never be
    retrieved into application memory for unauthorized users.
    """

    def __init__(
        self,
        repository: EvidenceRepository | None = None,
        permissions: PermissionService | None = None,
    ) -> None:
        self.repository: EvidenceRepository = repository or EvidenceRepository()
        self.permissions: PermissionService = permissions or PermissionService()
    
    @traced(
    name="Retrieval.DatabaseHybridRetriever",
    run_type="retriever",
)

    def retrieve(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        query: str,
        k: int = 8,
    ) -> list[dict[str, Any]]:
        with log_stage(
            logger,
            "rag.database_hybrid.retrieve",
            user_id=user_id,
            opportunity_id=opportunity_id,
            k=k,
        ):
            authorization: dict[str, Any] = self.permissions.authorize_opportunity(
                user_id,
                opportunity_id,
            )

            profile: dict[str, Any] = authorization["profile"]
            opportunity: dict[str, Any] = authorization["opportunity"]

            account_id: str = str(opportunity["account_id"])

            allowed_source_types: list[str] = sorted(
                self.permissions.allowed_source_types(profile),
            )

            allowed_access_levels: list[str] = self.permissions.allowed_access_levels(profile)

            return self.repository.search_keyword(
                opportunity_id=opportunity_id,
                account_id=account_id,
                allowed_source_types=allowed_source_types,
                allowed_access_levels=allowed_access_levels,
                query=query,
                k=k,
            )
