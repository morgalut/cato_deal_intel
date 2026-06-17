# Production Design Patterns Added

This version reorganizes the project so the implementation is closer to a production FastAPI service.

## 1. Endpoint Separation

All HTTP endpoints are now under:

```text
app/api/endpoints/
  health.py
  ingest.py
  briefs.py
```

`app/main.py` only creates the application and registers routers. This avoids the common anti-pattern where endpoint logic, dependencies, schemas, and business workflow are mixed in one file.

## 2. Dedicated Dependencies Layer

FastAPI dependency providers are under:

```text
app/dependencies/container.py
```

This supports dependency injection for:

- database connections
- repositories
- LLM clients
- workflows

This makes tests easier because a test can replace the real repository or LLM with a fake implementation.

## 3. Repository Design Pattern

Database access moved to:

```text
app/repositories/
  database.py
  evidence_repository.py
  base.py
```

The endpoint does not know SQL. The workflow does not know SQL. The repository owns persistence concerns.

Current repositories:

- `EvidenceRepository`: writes normalized evidence and performs permission-ready keyword retrieval.
- `Database`: connection factory.
- `EvidenceRepositoryProtocol`: typing contract for future mocks and alternative implementations.

## 4. Application Factory Pattern

`app/main.py` exposes:

```python
create_app() -> FastAPI
```

This supports cleaner testing and production bootstrapping.

## 5. Adapter Pattern for Source Loading

`EvidenceLoader` adapts different source formats into one evidence contract:

```text
Salesforce TSV
Gong TSV
Gong MD transcripts
Pricing TSV
Policy MD
Slack TSV
        ↓
Normalized Evidence Document
```

Every evidence document keeps:

- `stable_source_id`
- `source_file`
- `source_type`
- `opportunity_id`
- `account_id`
- `source_access_level`
- `content`
- `metadata`

## 6. Orchestrator Pattern

`BriefWorkflow` is the orchestrator. It controls order, state flow, partial failure points, and approval routing.

The flow is:

```text
Permission check
  ↓
Hybrid RAG retrieval
  ↓
Deal Context Agent
  ↓
Conversation Intelligence Agent
  ↓
Stakeholder Agent
  ↓
Negotiation Strategy Agent
  ↓
Approval routing
  ↓
Brief output + trace
```

## 7. Guarded LLM Pattern

The LLM is not used for ingestion or permission checks.

The model is only used after:

1. opportunity authorization
2. source-type filtering
3. access-level filtering
4. retrieval and citation construction

This lowers cost, reduces hallucination risk, and avoids leaking unauthorized data.

## 8. Hybrid RAG Pattern

The retrieval design remains:

```text
metadata filter + permission filter + lexical score + semantic score + recency/source boosts
```

Production upgrade path:

- PostgreSQL full-text search for keyword search
- pgvector cosine similarity for embeddings
- reciprocal rank fusion / weighted score fusion
- citation validation
- source reliability scoring

## 9. Typed Contracts

New API schemas are under:

```text
app/schemas/api.py
```

The updated code adds type hints to endpoint functions, dependency providers, repositories, loader methods, and workflow methods.

## 10. Logging Boundaries

Each layer logs its own lifecycle:

- API endpoint start/end
- loader file reads
- repository ingestion/search
- workflow start/end
- permission checks
- RAG retrieval details
- LLM calls
- approval routing

The logs are structured JSON-friendly events, suitable for OpenTelemetry, LangSmith, Datadog, or ELK.
