# Deep PLA: Logging, LLM Usage, Hybrid RAG, DB Ingestion

## 1. Product Logic
The requested product is a Strategic Deal Intelligence Assistant for negotiation preparation. It must not act like a generic chatbot. It must produce a grounded, permission-safe, auditable brief for a specific `opportunity_id` and `user_id`.

The system must use the task data only:
- Salesforce: accounts, opportunities, contacts
- Gong: call summaries and transcripts
- Pricing notes
- Access permissions
- Deal Desk policy
- Candidate-generated synthetic Slack updates

## 2. PLA Breakdown

### P — Perceive
The system first loads and normalizes evidence into a single document format:

```json
{
  "stable_source_id": "CALL-027",
  "source_file": "synthetic_data/gong/transcripts/OPP-1003_CALL-027.md",
  "source_type": "gong",
  "opportunity_id": "OPP-1003",
  "account_id": "ACC-2003",
  "source_access_level": "sensitive_pricing",
  "content": "...",
  "metadata": {...}
}
```

This format is critical because it allows deterministic filtering before RAG and before LLM generation.

### L — Link
The system links data by stable IDs:
- `opportunity_id` links Salesforce, Gong, Pricing, Slack.
- `account_id` links opportunities to accounts and contacts.
- `call_id`, `pricing_note_id`, and `update_id` become citation anchors.

### A — Act
The workflow then executes:
1. Authorize opportunity access.
2. Retrieve allowed evidence with Hybrid RAG.
3. Run specialized agents.
4. Route sensitive recommendations to approval.
5. Generate a structured brief with citations and warnings.
6. Persist logs/traces/briefs/approvals.

## 3. Logging Strategy
Every step logs:
- `stage.start`
- `stage.success`
- `stage.error`
- duration in milliseconds
- safe metadata: run id, opportunity id, agent name, tool name, count of documents, citation ids

No denied source content is logged.

Main logging files:
- `app/observability/logging.py`
- `app/observability/tracing.py`

Example log:

```json
{
  "event": "stage.success",
  "stage": "rag.retrieve",
  "opportunity_id": "OPP-1003",
  "returned": 8,
  "filtered_permission": 3,
  "duration_ms": 12.4
}
```

## 4. Dedicated DB Ingestion Endpoint
Brief generation should not reload and reparse raw files every time in production. Therefore the project now has:

```http
POST /ingest/load
```

Request:

```json
{
  "data_dir": "data",
  "truncate": true
}
```

This endpoint performs:
1. File loading.
2. Normalization.
3. Metadata enrichment.
4. Insertion into PostgreSQL documents table.
5. Logs for each stage.

The endpoint does not call the LLM. This saves cost and makes ingestion deterministic.

## 5. Hybrid RAG Emphasis
Hybrid RAG is used because deal intelligence has both exact identifiers and semantic language:

### Keyword retrieval is needed for:
- `OPP-1003`
- `CALL-027`
- `discount`
- `liability`
- `payment schedule`
- `restricted workflow`

### Semantic retrieval is needed for:
- buyer concerns
- negotiation posture
- ambiguity
- missing information
- stakeholder intent

The local prototype uses:
- BM25-like lexical scoring
- deterministic semantic proxy
- recency boost
- Slack source boost
- metadata filtering
- permission filtering

Production path:
- PostgreSQL + pgvector
- `text-embedding-3-small` or similar embedding model
- `tsvector` / BM25 keyword search
- Reciprocal Rank Fusion or weighted score merge
- metadata filters in SQL before ranking

## 6. Efficient LLM Usage
The LLM is used only where it adds value:

Used for:
- extracting buyer goals from retrieved snippets
- identifying ambiguity/conflicts
- synthesizing recommendations
- drafting executive summary sections

Not used for:
- permission checks
- loading TSV files
- parsing stable IDs
- approval rule thresholds
- metadata filtering
- deterministic validation

Implementation:
- `app/services/llm.py`
- model routing with cheap model for extraction/classification
- stronger model for sensitive synthesis
- temperature `0.1`
- JSON output mode
- compact evidence snippets only
- token usage logs

## 7. LangSmith and Debugging Tools
Recommended debugging stack:

- LangSmith: prompt, model, tool-call, chain and agent traces
- OpenTelemetry: service-level spans
- structlog JSON logs: local and container logs
- PostgreSQL trace table: durable audit events
- JSONL trace files: replayable local debugging
- pytest fixtures: regression tests for permissions and citations
- prompt-injection tests: validate that source content cannot override system policy

Important LLM debugging phases:
1. Prompt input inspection.
2. Retrieved evidence inspection.
3. Permission filter inspection.
4. Citation validation.
5. JSON schema validation.
6. Approval routing inspection.
7. Final brief safety check.

## 8. Skill and Tool Design

### Skills
- `hybrid_rag_skill.md`: retrieval strategy, ranking, citation rules.
- `approval_routing_skill.md`: policy-based approval flow.
- `llm_debugging_skill.md`: LangSmith, logs, traces, replay.

### Tools
- `RetrieveEvidenceTool`: retrieves only permission-allowed evidence.
- `ApprovalRouterTool`: routes sensitive recommendations.
- `GuardrailTool`: blocks unsupported or unsafe customer-facing language.
- `EvidenceRepository`: DB ingestion and keyword search.
- `LLMClient`: model routing and JSON generation.

## 9. Production Notes
For production:
- ingestion runs as async job
- embedding generated during ingestion
- vector index maintained in pgvector
- traces exported to LangSmith + OTEL collector
- secrets stored in Vault or cloud secret manager
- API protected by real auth/JWT
- approval queue integrated with Salesforce/Slack/Jira
- strict audit retention policy
