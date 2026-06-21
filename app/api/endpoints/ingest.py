from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.dependencies.container import get_evidence_repository
from app.observability.logging import get_logger, log_stage
from app.rag.loader import EvidenceLoader
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.api_models import IngestRequest

logger = get_logger("api.ingest")

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"],
)


@router.post("/load")
def load_evidence_to_db(
    req: IngestRequest,
    repository: Annotated[
        EvidenceRepository,
        Depends(get_evidence_repository),
    ],
) -> dict[str, Any]:
    """Load all local task data into PostgreSQL.

    This endpoint is deterministic:
    - loads access permissions;
    - loads opportunities;
    - loads normalized evidence documents;
    - does not call the LLM.
    """

    with log_stage(
        logger,
        "api.ingest.load",
        data_dir=req.data_dir,
        truncate=req.truncate,
    ):
        reference_result: dict[str, Any] = repository.ingest_reference_tables(
            data_dir=req.data_dir,
            truncate=req.truncate,
        )

        docs: list[dict[str, Any]] = EvidenceLoader(req.data_dir).load_documents()

        document_result: dict[str, Any] = repository.ingest_documents(
            docs,
            truncate=req.truncate,
        )

        return {
            "status": "ok",
            **reference_result,
            **document_result,
        }