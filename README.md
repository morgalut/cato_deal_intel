# Cato Deal Intelligence Assistant

Production-minded Agentic AI prototype for generating secure Strategic Deal Intelligence Briefs.

The system uses:

* FastAPI
* PostgreSQL + pgvector
* DB-backed Hybrid RAG
* Permission filtering before retrieval
* Post-generation citation validation
* LLM-backed agents
* Human-in-the-loop approval flow
* Persistent traces, approvals, and generated briefs

---

## 1. Start PostgreSQL

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

Reset database completely:

```bash
docker compose down -v
docker compose up -d postgres
```

---

## 2. Create Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Environment variables

Create `.env`:

```env
DATABASE_URL=postgresql://deal:deal@localhost:5432/deal_intel

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_CHEAP_MODEL=gpt-4.1-nano

LLM_MODE=offline
LOG_LEVEL=INFO

LANGSMITH_TRACING=false
LANGCHAIN_PROJECT=cato-deal-intelligence
```

For live LLM mode:

```env
LLM_MODE=live
OPENAI_API_KEY=your_key_here
```
If We run in docker-compose 
```env

DATABASE_URL=postgresql://deal:deal@postgres:5432/deal_intel
```
---

## 4. Run API

```bash
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://localhost:8000/docs
```

---

## 5. Health check

```bash
curl -X GET "http://localhost:8000/health"
```

---

## 6. Load all task data into DB

This loads:

* `access_permissions`
* `opportunities`
* `documents`

```bash
curl -X POST "http://localhost:8000/ingest/load" \
  -H "Content-Type: application/json" \
  -d '{
    "data_dir": "data",
    "truncate": true
  }'
```

Expected result:

```json
{
  "status": "ok",
  "ingested_permissions": 3,
  "ingested_opportunities": 3,
  "ingested_documents": 30,
  "truncate": true
}
```

---

## 7. Generate a brief

Authorized example:

```bash
curl -X POST "http://localhost:8000/briefs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USR-5001",
    "opportunity_id": "OPP-1001"
  }'
```

Sensitive opportunity example:

```bash
curl -X POST "http://localhost:8000/briefs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USR-5001",
    "opportunity_id": "OPP-1003"
  }'
```

Unauthorized example:

```bash
curl -X POST "http://localhost:8000/briefs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USR-5007",
    "opportunity_id": "OPP-1003"
  }'
```

Expected result:

```json
{
  "detail": "Access denied"
}
```

---

## 8. Approval endpoints

List pending approvals:

```bash
curl -X GET "http://localhost:8000/approvals/pending"
```

List pending approvals for one opportunity:

```bash
curl -X GET "http://localhost:8000/approvals/pending?opportunity_id=OPP-1001"
```

Approve request:

```bash
curl -X POST "http://localhost:8000/approvals/APR_EXAMPLE_ID/approve?reviewer_id=USR-MANAGER-1&reason=Approved"
```

Reject request:

```bash
curl -X POST "http://localhost:8000/approvals/APR_EXAMPLE_ID/reject?reviewer_id=USR-MANAGER-1&reason=Rejected"
```

---

## 9. Run demo script

```bash
PYTHONPATH=. python scripts/run_demo.py \
  --user USR-5001 \
  --opp OPP-1001 \
  --out artifacts/brief_OPP-1001.json
```

Sensitive deal:

```bash
PYTHONPATH=. python scripts/run_demo.py \
  --user USR-5001 \
  --opp OPP-1003 \
  --out artifacts/brief_OPP-1003.json
```

---

## 10. Inspect database manually

Connect:

```bash
docker exec -it cato-deal-intel-postgres psql -U deal -d deal_intel
```

Check loaded permissions:

```sql
SELECT user_id, role, allowed_account_ids, allowed_source_types
FROM access_permissions;
```

Check opportunities:

```sql
SELECT opportunity_id, account_id, risk_level, restricted_access
FROM opportunities;
```

Check documents:

```sql
SELECT source_type, source_access_level, COUNT(*)
FROM documents
GROUP BY source_type, source_access_level;
```

Check approvals:

```sql
SELECT approval_id, opportunity_id, status, approval_types
FROM approval_requests
ORDER BY created_at DESC;
```

Check traces:

```sql
SELECT run_id, event_type, actor, created_at
FROM trace_events
ORDER BY created_at DESC
LIMIT 20;
```

Check saved briefs:

```sql
SELECT brief_id, run_id, user_id, opportunity_id, created_at
FROM generated_briefs
ORDER BY created_at DESC;
```

---

## 11. Run quality checks

```bash
ruff check . --fix
ruff format .
python -m mypy app scripts tests
```

Run tests:

```bash
pytest -q
```

---

## 12. Expected end-to-end flow

```text
1. docker compose up -d postgres
2. uvicorn app.main:app --reload
3. POST /ingest/load
4. POST /briefs/generate
5. System checks permissions
6. System retrieves only allowed evidence from DB
7. Agents generate grounded findings and recommendations
8. Approval router creates pending approvals if needed
9. Permission service validates final citations
10. Trace events are saved
11. Brief is saved
12. API returns safe response
```

---

## 13. Main security guarantees

The system enforces:

* Permission check before retrieval
* DB-level evidence scope filtering
* No file-based retrieval in production workflow
* Structured LLM output validation
* Deterministic approval routing
* Post-generation citation validation
* Persistent audit traces
* Persistent approval state
* Persistent generated briefs

---

## 14. Important note

Before generating briefs, always run:

```bash
curl -X POST "http://localhost:8000/ingest/load" \
  -H "Content-Type: application/json" \
  -d '{"data_dir":"data","truncate":true}'
```

Without this step, the DB-backed `PermissionService` and `DatabaseHybridRetriever` will not have the required data.
