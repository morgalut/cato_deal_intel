from __future__ import annotations

import json
import uuid
from typing import Any

from app.contracts.brief import BriefMetadata, StrategicDealBrief
from app.observability.logging import get_logger, log_stage
from app.repositories.database import Database
from app.security.permissions import PermissionService

logger = get_logger("repository.brief")


class BriefRepository:
    """Repository for persisted Strategic Deal Intelligence Briefs."""

    def __init__(
        self,
        db: Database | None = None,
        permissions: PermissionService | None = None,
    ) -> None:
        self.db: Database = db or Database()
        self.permissions: PermissionService = permissions or PermissionService()

    def save_brief(
        self,
        *,
        run_id: str,
        user_id: str,
        opportunity_id: str,
        brief: StrategicDealBrief,
    ) -> BriefMetadata:
        brief_id: str = f"BRF-{uuid.uuid4().hex[:12]}"
        brief_json: str = brief.model_dump_json()

        with (
            log_stage(
                logger,
                "brief.save",
                brief_id=brief_id,
                run_id=run_id,
                user_id=user_id,
                opportunity_id=opportunity_id,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO generated_briefs (
                    brief_id,
                    run_id,
                    user_id,
                    opportunity_id,
                    brief_json
                )
                VALUES (%s,%s,%s,%s,%s::jsonb)
                RETURNING
                    brief_id,
                    run_id,
                    user_id,
                    opportunity_id,
                    created_at
                """,
                (
                    brief_id,
                    run_id,
                    user_id,
                    opportunity_id,
                    brief_json,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            return self._row_to_metadata(cur, row)

    def get_brief(
        self,
        *,
        user_id: str,
        brief_id: str,
    ) -> StrategicDealBrief | None:
        with (
            log_stage(
                logger,
                "brief.get",
                user_id=user_id,
                brief_id=brief_id,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT opportunity_id, brief_json
                FROM generated_briefs
                WHERE brief_id = %s
                """,
                (brief_id,),
            )

            row = cur.fetchone()

            if row is None:
                return None

            opportunity_id = str(self._get_value(cur, row, "opportunity_id", 0))

            self.permissions.authorize_opportunity(
                user_id,
                opportunity_id,
            )

            raw_brief = self._get_value(cur, row, "brief_json", 1)

            if isinstance(raw_brief, str):
                payload: dict[str, Any] = json.loads(raw_brief)
            else:
                payload = dict(raw_brief)

            return StrategicDealBrief.model_validate(payload)

    def list_for_opportunity(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        limit: int = 20,
    ) -> list[BriefMetadata]:
        self.permissions.authorize_opportunity(
            user_id,
            opportunity_id,
        )

        with (
            log_stage(
                logger,
                "brief.list_for_opportunity",
                user_id=user_id,
                opportunity_id=opportunity_id,
                limit=limit,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT
                    brief_id,
                    run_id,
                    user_id,
                    opportunity_id,
                    created_at
                FROM generated_briefs
                WHERE opportunity_id = %s
                  AND user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (
                    opportunity_id,
                    user_id,
                    limit,
                ),
            )

            return [self._row_to_metadata(cur, row) for row in cur.fetchall() if row is not None]

    def _row_to_metadata(
        self,
        cursor: Any,
        row: Any,
    ) -> BriefMetadata:
        data = self._row_to_dict(cursor, row)

        return BriefMetadata(
            brief_id=str(data["brief_id"]),
            run_id=str(data["run_id"]),
            user_id=str(data["user_id"]),
            opportunity_id=str(data["opportunity_id"]),
            created_at=str(data["created_at"]),
        )

    def _row_to_dict(
        self,
        cursor: Any,
        row: Any,
    ) -> dict[str, Any]:
        if row is None:
            return {}

        if isinstance(row, dict):
            return row

        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row, strict=False))

    def _get_value(
        self,
        cursor: Any,
        row: Any,
        key: str,
        index: int,
    ) -> Any:
        if isinstance(row, dict):
            return row[key]

        if cursor.description:
            columns = [description[0] for description in cursor.description]
            if key in columns:
                return row[columns.index(key)]

        return row[index]
