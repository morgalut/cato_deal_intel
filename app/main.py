from __future__ import annotations

from app.api.endpoints import briefs, health, ingest
from app.observability.logging import configure_logging
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Application factory.

    Design pattern: Application Factory. Keeps FastAPI bootstrapping separate from
    route definitions and makes tests/production deployment simpler.
    """

    configure_logging()
    app = FastAPI(title="Strategic Deal Intelligence Assistant")
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(briefs.router)
    return app


app: FastAPI = create_app()
