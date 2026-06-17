from __future__ import annotations

from app.rag.loader import EvidenceLoader
from app.repositories.database import Database
from app.repositories.evidence_repository import EvidenceRepository
from app.services.llm import LLMClient
from app.workflows.brief_workflow import BriefWorkflow


def get_database() -> Database:
    return Database()


def get_evidence_repository() -> EvidenceRepository:
    return EvidenceRepository(db=get_database())


def get_evidence_loader(data_dir: str = "data") -> EvidenceLoader:
    return EvidenceLoader(data_dir=data_dir)


def get_llm_client() -> LLMClient:
    return LLMClient()


def get_brief_workflow() -> BriefWorkflow:
    return BriefWorkflow(llm=get_llm_client())
