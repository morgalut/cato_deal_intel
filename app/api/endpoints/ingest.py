from __future__ import annotations

from typing import Annotated, Any

from app.dependencies.container import get_evidence_repository
from app.observability.logging import get_logger, log_stage
from app.rag.loader import EvidenceLoader
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.api_models import IngestRequest
from fastapi import APIRouter, Depends

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
    """Load synthetic evidence files into PostgreSQL.

    This endpoint is deterministic and must not call the LLM.
    LLM usage happens only after permission-filtered retrieval.
    """

    with log_stage(
        logger,
        "api.ingest.load",
        data_dir=req.data_dir,
        truncate=req.truncate,
    ):
        docs: list[dict[str, Any]] = EvidenceLoader(req.data_dir).load_documents()
        result: dict[str, Any] = repository.ingest_documents(
            docs,
            truncate=req.truncate,
        )

        return {
            "status": "ok",
            **result,
        }
