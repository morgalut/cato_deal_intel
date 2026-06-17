from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.observability.logging import get_logger, log_stage
from app.security.permissions import PermissionService

logger = get_logger("rag.hybrid")

WORD = re.compile(r"[A-Za-z0-9_%-]+")


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in WORD.findall(text)]


class LocalHybridRetriever:
    """Hybrid RAG for the home task.

    Retrieval stages:
    1. Authorization: verify requester can access the opportunity/account.
    2. Metadata filter: opportunity, account, source type, and access level.
    3. Keyword score: BM25-like lexical relevance.
    4. Semantic score: local deterministic proxy.
       Production should replace this with pgvector cosine similarity.
    5. Recency/source reliability boosts.
    6. Citation payload preservation.
    """

    def __init__(
        self,
        docs: list[dict[str, Any]],
        permission_service: PermissionService,
    ) -> None:
        self.docs: list[dict[str, Any]] = docs
        self.permissions: PermissionService = permission_service
        self.doc_tokens: list[list[str]] = [tokenize(doc["content"]) for doc in docs]
        self.df: Counter[str] = Counter(
            token for tokens in self.doc_tokens for token in set(tokens)
        )
        self.avgdl: float = sum(len(tokens) for tokens in self.doc_tokens) / max(
            1, len(self.doc_tokens)
        )

        logger.info(
            "rag.index.ready",
            documents=len(docs),
            avg_doc_tokens=round(self.avgdl, 2),
        )

    def keyword_score(self, query: str, idx: int) -> float:
        query_tokens: list[str] = tokenize(query)
        document_tokens: list[str] = self.doc_tokens[idx]
        term_frequency: Counter[str] = Counter(document_tokens)

        score: float = 0.0
        k1: float = 1.5
        b: float = 0.75
        total_documents: int = len(self.docs)

        for term in query_tokens:
            if term not in term_frequency:
                continue

            idf: float = math.log(
                1 + (total_documents - self.df[term] + 0.5) / (self.df[term] + 0.5)
            )

            denominator: float = term_frequency[term] + k1 * (
                1 - b + b * len(document_tokens) / self.avgdl
            )

            score += idf * (term_frequency[term] * (k1 + 1) / denominator)

        return score

    def semantic_score(self, query: str, idx: int) -> float:
        query_tokens: set[str] = set(tokenize(query))
        document_tokens: set[str] = set(self.doc_tokens[idx])

        return len(query_tokens & document_tokens) / max(
            1,
            len(query_tokens | document_tokens),
        )

    def retrieve(
        self,
        user_id: str,
        opportunity_id: str,
        query: str,
        k: int = 8,
    ) -> list[dict[str, Any]]:
        with log_stage(
            logger,
            "rag.retrieve",
            user_id=user_id,
            opportunity_id=opportunity_id,
            query=query,
            k=k,
        ):
            authorization: dict[str, Any] = self.permissions.authorize_opportunity(
                user_id,
                opportunity_id,
            )

            account_id: str = str(authorization["opportunity"]["account_id"])

            candidates: list[dict[str, Any]] = []
            filtered_scope: int = 0
            filtered_permission: int = 0

            for index, document in enumerate(self.docs):
                document_opportunity_id = document.get("opportunity_id")
                document_account_id = document.get("account_id")

                if document_opportunity_id not in (opportunity_id, None):
                    filtered_scope += 1
                    continue

                if document_account_id not in (account_id, None):
                    filtered_scope += 1
                    continue

                if not self.permissions.can_retrieve_doc(user_id, document):
                    filtered_permission += 1
                    continue

                keyword_score: float = self.keyword_score(query, index)
                semantic_score: float = self.semantic_score(query, index)
                recency_boost: float = 0.05 if "2026-04" in document.get("content", "") else 0.0
                source_boost: float = 0.15 if document.get("source_type") == "slack" else 0.0

                score: float = (
                    0.55 * keyword_score + 0.40 * semantic_score + recency_boost + source_boost
                )

                if score <= 0:
                    continue

                candidates.append(
                    {
                        **document,
                        "score": round(score, 4),
                        "keyword_score": round(keyword_score, 4),
                        "semantic_score": round(semantic_score, 4),
                    }
                )

            results: list[dict[str, Any]] = sorted(
                candidates,
                key=lambda result: result["score"],
                reverse=True,
            )[:k]

            logger.info(
                "rag.retrieve.result",
                opportunity_id=opportunity_id,
                returned=len(results),
                candidates=len(candidates),
                filtered_scope=filtered_scope,
                filtered_permission=filtered_permission,
                sources=[
                    f"{result['source_type']}:{result['stable_source_id']}" for result in results
                ],
            )

            return results
