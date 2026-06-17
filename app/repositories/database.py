from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from app.config import settings
from psycopg import Connection
from psycopg.rows import dict_row


class Database:
    """Small connection factory.

    Design pattern: Factory + dependency injection. The API layer receives this through
    FastAPI dependencies, which makes tests able to inject a fake DB without changing endpoints.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn: str = dsn or settings.database_url

    @contextmanager
    def connect(self) -> Iterator[Connection[dict[str, Any]]]:
        conn: Connection[dict[str, Any]] = psycopg.connect(self.dsn, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.close()
