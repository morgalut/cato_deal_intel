from __future__ import annotations

from functools import lru_cache

from app.rag.database_hybrid import DatabaseHybridRetriever
from app.rag.loader import EvidenceLoader
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.brief_repository import BriefRepository
from app.repositories.database import Database
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.trace_repository import TraceRepository
from app.security.permissions import PermissionService
from app.services.llm import LLMClient
from app.workflows.brief_workflow import BriefWorkflow
from app.services.cost_manager import CostManager

# =====================================================================
# 1. CORE INFRASTRUCTURE LAYER (Cached Singletons)
# =====================================================================

def get_cost_manager() -> CostManager:
    return CostManager()


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Core database adapter - shared singleton connection pool."""
    return Database()


def get_llm_client() -> LLMClient:
    return LLMClient(
        cost_manager=get_cost_manager(),
    )


# =====================================================================
# 2. SECURITY & AUTHORIZATION LAYER (Cached Singleton)
# =====================================================================


@lru_cache(maxsize=1)
def get_permission_service() -> PermissionService:
    """Security guardrail enforcing pre-retrieval and post-generation MAC."""
    return PermissionService(
        db=get_database(),
    )


# =====================================================================
# 3. REPOSITORY PERSISTENCE LAYER (Cached Singletons)
# =====================================================================


@lru_cache(maxsize=1)
def get_evidence_repository() -> EvidenceRepository:
    return EvidenceRepository(
        db=get_database(),
    )


@lru_cache(maxsize=1)
def get_approval_repository() -> ApprovalRepository:
    return ApprovalRepository(
        db=get_database(),
    )


@lru_cache(maxsize=1)
def get_trace_repository() -> TraceRepository:
    return TraceRepository(
        db=get_database(),
    )


@lru_cache(maxsize=1)
def get_brief_repository() -> BriefRepository:
    """Clean Data Access Layer without leaking permission service inside."""
    return BriefRepository(
        db=get_database(),
    )


# =====================================================================
# 4. RAG & INGESTION LAYER (Cached Singletons)
# =====================================================================


@lru_cache(maxsize=1)
def get_database_hybrid_retriever() -> DatabaseHybridRetriever:
    """Secure RAG Retriever - bridges data access with security scoping."""
    return DatabaseHybridRetriever(
        repository=get_evidence_repository(),
        permissions=get_permission_service(),
    )


@lru_cache(maxsize=1)
def get_evidence_loader() -> EvidenceLoader:
    return EvidenceLoader(
        data_dir="data",
    )


# =====================================================================
# 5. ORCHESTRATION & AGENTIC WORKFLOW LAYER (Cached Singleton)
# =====================================================================


@lru_cache(maxsize=1)
def get_brief_workflow() -> BriefWorkflow:
    """The main orchestration engine composing all enterprise dependencies."""
    return BriefWorkflow(
        llm=get_llm_client(),
        permissions=get_permission_service(),
        retriever=get_database_hybrid_retriever(),
        approval_repository=get_approval_repository(),
        trace_repository=get_trace_repository(),
        brief_repository=get_brief_repository(),
    )


def reset_container_cache() -> None:
    """Utility helper to clear cache between test runs (Crucial for Pytest)."""
    get_database.cache_clear()
    get_llm_client.cache_clear()
    get_permission_service.cache_clear()
    get_evidence_repository.cache_clear()
    get_approval_repository.cache_clear()
    get_trace_repository.cache_clear()
    get_brief_repository.cache_clear()
    get_database_hybrid_retriever.cache_clear()
    get_evidence_loader.cache_clear()
    get_brief_workflow.cache_clear()
