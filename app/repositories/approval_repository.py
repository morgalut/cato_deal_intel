from __future__ import annotations

import json
import uuid
from typing import Any

from app.contracts.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalRequestRecord,
)
from app.observability.logging import get_logger, log_stage
from app.repositories.database import Database

logger = get_logger("repository.approvals")


class ApprovalRepository:
    """Repository for human-in-the-loop approval state."""

    def __init__(self, db: Database | None = None) -> None:
        self.db: Database = db or Database()

    def create_request(self, request: ApprovalRequest) -> ApprovalRequestRecord:
        approval_id: str = f"APR-{uuid.uuid4().hex[:12]}"

        citations_json: str = json.dumps(
            [citation.model_dump() for citation in request.citations],
            ensure_ascii=False,
        )

        with (
            log_stage(
                logger,
                "approval.create",
                approval_id=approval_id,
                recommendation_id=request.recommendation_id,
                opportunity_id=request.opportunity_id,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO approval_requests (
                    approval_id,
                    recommendation_id,
                    opportunity_id,
                    action_text,
                    approval_types,
                    status,
                    requested_by,
                    citations
                )
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)
                RETURNING
                    approval_id,
                    recommendation_id,
                    opportunity_id,
                    action_text,
                    approval_types,
                    status,
                    requested_by,
                    reviewer_id,
                    decision_reason,
                    citations,
                    created_at,
                    decided_at
                """,
                (
                    approval_id,
                    request.recommendation_id,
                    request.opportunity_id,
                    request.action_text,
                    json.dumps(request.approval_types, ensure_ascii=False),
                    request.status,
                    request.requested_by,
                    citations_json,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            return ApprovalRequestRecord.model_validate(
                self._row_to_dict(cur, row),
            )

    def decide(self, decision: ApprovalDecision) -> ApprovalRequestRecord | None:
        with (
            log_stage(
                logger,
                "approval.decide",
                approval_id=decision.approval_id,
                reviewer_id=decision.reviewer_id,
                status=decision.status,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                UPDATE approval_requests
                SET
                    status = %s,
                    reviewer_id = %s,
                    decision_reason = %s,
                    decided_at = NOW()
                WHERE approval_id = %s
                RETURNING
                    approval_id,
                    recommendation_id,
                    opportunity_id,
                    action_text,
                    approval_types,
                    status,
                    requested_by,
                    reviewer_id,
                    decision_reason,
                    citations,
                    created_at,
                    decided_at
                """,
                (
                    decision.status,
                    decision.reviewer_id,
                    decision.reason,
                    decision.approval_id,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            if row is None:
                return None

            return ApprovalRequestRecord.model_validate(
                self._row_to_dict(cur, row),
            )

    def list_pending(
        self,
        opportunity_id: str | None = None,
    ) -> list[ApprovalRequestRecord]:
        with (
            log_stage(
                logger,
                "approval.list_pending",
                opportunity_id=opportunity_id,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT
                    approval_id,
                    recommendation_id,
                    opportunity_id,
                    action_text,
                    approval_types,
                    status,
                    requested_by,
                    reviewer_id,
                    decision_reason,
                    citations,
                    created_at,
                    decided_at
                FROM approval_requests
                WHERE status = 'pending_approval'
                  AND (%s::text IS NULL OR opportunity_id = %s::text)
                ORDER BY created_at DESC
                """,
                (
                    opportunity_id,
                    opportunity_id,
                ),
            )

            return [
                ApprovalRequestRecord.model_validate(
                    self._row_to_dict(cur, row),
                )
                for row in cur.fetchall()
            ]

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