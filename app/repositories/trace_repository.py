from __future__ import annotations

import json

from app.contracts.brief import TraceEvent
from app.observability.logging import get_logger, log_stage
from app.repositories.database import Database

logger = get_logger("repository.trace")


class TraceRepository:
    """Persistence layer for workflow traces."""

    def __init__(
        self,
        db: Database | None = None,
    ) -> None:
        self.db: Database = db or Database()

    def save_event(
        self,
        *,
        event: TraceEvent,
    ) -> None:
        with (
            log_stage(
                logger,
                "trace.save_event",
                run_id=event.run_id,
                event_type=event.event_type,
                actor=event.actor,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO trace_events (
                    run_id,
                    event_type,
                    actor,
                    payload
                )
                VALUES (%s,%s,%s,%s::jsonb)
                """,
                (
                    event.run_id,
                    event.event_type,
                    event.actor,
                    json.dumps(
                        event.payload,
                        ensure_ascii=False,
                    ),
                ),
            )

            conn.commit()

    def save_batch(
        self,
        *,
        events: list[TraceEvent],
    ) -> None:
        if not events:
            return

        run_id: str = events[0].run_id

        rows: list[tuple[str, str, str, str]] = [
            (
                event.run_id,
                event.event_type,
                event.actor,
                json.dumps(
                    event.payload,
                    ensure_ascii=False,
                ),
            )
            for event in events
        ]

        with (
            log_stage(
                logger,
                "trace.save_batch",
                run_id=run_id,
                count=len(events),
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.executemany(
                """
                INSERT INTO trace_events (
                    run_id,
                    event_type,
                    actor,
                    payload
                )
                VALUES (%s,%s,%s,%s::jsonb)
                """,
                rows,
            )

            conn.commit()

    def get_run(
        self,
        run_id: str,
    ) -> list[TraceEvent]:
        with (
            log_stage(
                logger,
                "trace.get_run",
                run_id=run_id,
            ),
            self.db.connect() as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT
                    EXTRACT(EPOCH FROM created_at) AS ts,
                    run_id,
                    event_type,
                    actor,
                    payload
                FROM trace_events
                WHERE run_id = %s
                ORDER BY created_at ASC
                """,
                (run_id,),
            )

            rows = cur.fetchall()

            return [
                TraceEvent(
                    ts=float(row["ts"]),
                    run_id=str(row["run_id"]),
                    event_type=str(row["event_type"]),
                    actor=str(row["actor"]),
                    payload=dict(row["payload"]),
                )
                for row in rows
            ]
