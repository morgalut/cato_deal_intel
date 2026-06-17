from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from app.observability.logging import get_logger, log_stage
from app.repositories.database import Database

logger = get_logger("repository.evidence")


class EvidenceRepository:
    """Repository Pattern for evidence persistence and retrieval."""

    def __init__(self, db: Database | None = None) -> None:
        self.db: Database = db or Database()

    def ingest_documents(
        self,
        documents: Iterable[dict[str, Any]],
        truncate: bool = False,
    ) -> dict[str, Any]:
        docs: list[dict[str, Any]] = list(documents)

        with (
            log_stage(
                logger,
                "repository.evidence.ingest",
                document_count=len(docs),
                truncate=truncate,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            if truncate:
                cur.execute("TRUNCATE documents RESTART IDENTITY")

            for doc in docs:
                cur.execute(
                    """
                    INSERT INTO documents (
                      stable_source_id,
                      source_file,
                      source_type,
                      opportunity_id,
                      account_id,
                      source_access_level,
                      sensitivity,
                      content,
                      metadata
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    """,
                    (
                        doc["stable_source_id"],
                        doc["source_file"],
                        doc["source_type"],
                        doc.get("opportunity_id"),
                        doc.get("account_id"),
                        doc.get("source_access_level", "standard"),
                        doc.get(
                            "sensitivity",
                            doc.get("source_access_level", "standard"),
                        ),
                        doc["content"],
                        json.dumps(
                            doc.get("metadata", {}),
                            ensure_ascii=False,
                        ),
                    ),
                )

            conn.commit()

        return {
            "ingested_documents": len(docs),
            "truncate": truncate,
        }

    def search_keyword(
        self,
        *,
        opportunity_id: str,
        account_id: str | None,
        allowed_source_types: list[str],
        allowed_access_levels: list[str],
        query: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        with (
            log_stage(
                logger,
                "repository.evidence.keyword_search",
                opportunity_id=opportunity_id,
                account_id=account_id,
                allowed_source_types=allowed_source_types,
                allowed_access_levels=allowed_access_levels,
                k=k,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT *,
                       ts_rank_cd(
                         search_tsv,
                         plainto_tsquery('english', %s)
                       ) AS keyword_score
                FROM documents
                WHERE (opportunity_id = %s OR opportunity_id IS NULL)
                  AND (%s IS NULL OR account_id = %s OR account_id IS NULL)
                  AND source_type = ANY(%s)
                  AND source_access_level = ANY(%s)
                  AND search_tsv @@ plainto_tsquery('english', %s)
                ORDER BY keyword_score DESC, created_at DESC
                LIMIT %s
                """,
                (
                    query,
                    opportunity_id,
                    account_id,
                    account_id,
                    allowed_source_types,
                    allowed_access_levels,
                    query,
                    k,
                ),
            )

            return list(cur.fetchall())
