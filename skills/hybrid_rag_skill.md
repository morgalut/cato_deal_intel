# Skill: Hybrid Deal Evidence Retrieval

Purpose: retrieve only allowed evidence for a strategic opportunity before any LLM synthesis.

Inputs:
- user_id
- opportunity_id
- query
- allowed_source_types from access_permissions.tsv

Process:
1. Authorize opportunity/account access.
2. Filter source_type, account_id, opportunity_id, and source_access_level.
3. Run hybrid retrieval:
   - keyword search: PostgreSQL full text / BM25-like score
   - vector search: pgvector cosine similarity from OpenAI embeddings
   - metadata filters: opportunity_id, account_id, source_type, source_access_level
   - optional recency/source reliability boost
4. Return evidence with stable citation IDs only.

Failure modes:
- Unknown user: deny.
- Unauthorized opportunity: deny without metadata leakage.
- No evidence: return empty evidence and warning.
- Restricted/sensitive source: omit before agent context creation.

Production DB design:
- documents.content
- documents.embedding vector(1536)
- documents.search_tsv tsvector
- metadata JSONB
