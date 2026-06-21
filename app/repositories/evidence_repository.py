from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
from app.observability.logging import get_logger, log_stage
from app.repositories.database import Database

logger = get_logger("repository.evidence")


class EvidenceRepository:
    """Repository Pattern for evidence persistence and retrieval.

    Responsibilities:
    - ingest reference tables required by DB-backed permissions;
    - ingest normalized RAG documents;
    - query only permission-scoped evidence.
    """

    def __init__(self, db: Database | None = None) -> None:
        self.db: Database = db or Database()

    def ingest_reference_tables(
        self,
        *,
        data_dir: str,
        truncate: bool = False,
    ) -> dict[str, Any]:
        root: Path = Path(data_dir)

        permissions_path: Path = root / "policies" / "access_permissions.tsv"
        opportunities_path: Path = root / "salesforce" / "opportunities.tsv"

        permissions = pd.read_csv(
            permissions_path,
            sep="\t",
        )

        opportunities = pd.read_csv(
            opportunities_path,
            sep="\t",
        )

        with (
            log_stage(
                logger,
                "repository.reference.ingest",
                permissions=len(permissions),
                opportunities=len(opportunities),
                truncate=truncate,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            if truncate:
                cur.execute("TRUNCATE access_permissions RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE opportunities RESTART IDENTITY CASCADE")

            for _, row in permissions.iterrows():
                allowed_account_ids: list[str] = self._parse_array_field(
                    row["allowed_account_ids"],
                )
                allowed_source_types: list[str] = self._parse_array_field(
                    row["allowed_source_types"],
                )

                cur.execute(
                    """
                    INSERT INTO access_permissions (
                        user_id,
                        role,
                        allowed_account_ids,
                        allowed_source_types,
                        can_view_restricted_account,
                        can_view_sensitive_pricing
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        role = EXCLUDED.role,
                        allowed_account_ids = EXCLUDED.allowed_account_ids,
                        allowed_source_types = EXCLUDED.allowed_source_types,
                        can_view_restricted_account =
                            EXCLUDED.can_view_restricted_account,
                        can_view_sensitive_pricing =
                            EXCLUDED.can_view_sensitive_pricing
                    """,
                    (
                        str(row["user_id"]),
                        str(row["role"]),
                        allowed_account_ids,
                        allowed_source_types,
                        self._to_bool(row["can_view_restricted_account"]),
                        self._to_bool(row["can_view_sensitive_pricing"]),
                    ),
                )

            for _, row in opportunities.iterrows():
                cur.execute(
                    """
                    INSERT INTO opportunities (
                        opportunity_id,
                        account_id,
                        account_name,
                        stage,
                        type,
                        acv,
                        tcv,
                        close_date,
                        owner,
                        risk_level,
                        restricted_access
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (opportunity_id) DO UPDATE SET
                        account_id = EXCLUDED.account_id,
                        account_name = EXCLUDED.account_name,
                        stage = EXCLUDED.stage,
                        type = EXCLUDED.type,
                        acv = EXCLUDED.acv,
                        tcv = EXCLUDED.tcv,
                        close_date = EXCLUDED.close_date,
                        owner = EXCLUDED.owner,
                        risk_level = EXCLUDED.risk_level,
                        restricted_access = EXCLUDED.restricted_access
                    """,
                    (
                        str(row["opportunity_id"]),
                        str(row["account_id"]),
                        str(row["account_name"]),
                        str(row["stage"]),
                        str(row["type"]),
                        float(row["acv"]),
                        float(row["tcv"]),
                        str(row["close_date"]),
                        str(row["owner"]),
                        str(row["risk_level"]),
                        self._to_bool(row["restricted_access"]),
                    ),
                )

            conn.commit()

        return {
            "ingested_permissions": len(permissions),
            "ingested_opportunities": len(opportunities),
        }

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
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
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
                        plainto_tsquery('english', %s::text)
                    ) AS keyword_score
                FROM documents
                WHERE (opportunity_id = %s::text OR opportunity_id IS NULL)
                AND (
                    %s::text IS NULL
                    OR account_id = %s::text
                    OR account_id IS NULL
                )
                AND source_type = ANY(%s::text[])
                AND source_access_level = ANY(%s::text[])
                AND search_tsv @@ plainto_tsquery('english', %s::text)
                ORDER BY keyword_score DESC, created_at DESC
                LIMIT %s::int
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

            rows = cur.fetchall()

            if rows:
                return [self._row_to_dict(cur, row) for row in rows]

            logger.info(
                "repository.evidence.keyword_search.empty_fallback",
                opportunity_id=opportunity_id,
                account_id=account_id,
                query=query,
            )

            cur.execute(
                """
                SELECT *,
                    0.0 AS keyword_score
                FROM documents
                WHERE (opportunity_id = %s::text OR opportunity_id IS NULL)
                AND (
                    %s::text IS NULL
                    OR account_id = %s::text
                    OR account_id IS NULL
                )
                AND source_type = ANY(%s::text[])
                AND source_access_level = ANY(%s::text[])
                ORDER BY
                    CASE
                        WHEN opportunity_id = %s::text THEN 0
                        WHEN account_id = %s::text THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT %s::int
                """,
                (
                    opportunity_id,
                    account_id,
                    account_id,
                    allowed_source_types,
                    allowed_access_levels,
                    opportunity_id,
                    account_id,
                    k,
                ),
            )

            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def _parse_array_field(
        self,
        value: Any,
    ) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        return [item.strip() for item in str(value).split(",") if item.strip()]

    def _to_bool(
        self,
        value: Any,
    ) -> bool:
        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
        }

    def _row_to_dict(
        self,
        cursor: Any,
        row: Any,
    ) -> dict[str, Any]:
        if isinstance(row, dict):
            return row

        columns = [description[0] for description in cursor.description]

        return dict(zip(columns, row, strict=False))
