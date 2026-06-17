# Cato Strategic Deal Intelligence Assistant

Runnable prototype scaffold for the Agentic AI Engineer home task.

## Run DB
```bash
docker compose up -d postgres
```

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run demo
```bash
python scripts/run_demo.py --user USR-5001 --opp OPP-1001 --out artifacts/opp1001.json
python scripts/run_demo.py --user USR-5003 --opp OPP-1003 --out artifacts/opp1003.json
python scripts/run_demo.py --user USR-5007 --opp OPP-1003
```

## Run API
```bash
uvicorn app.main:app --reload
curl -X POST http://localhost:8000/briefs/generate \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"USR-5001","opportunity_id":"OPP-1001"}'
```

## LangSmith
Set:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=cato-deal-intelligence
```

## Notes
This scaffold includes deterministic local fallback logic so the architecture can be inspected without keys. In the final exam run, replace the extraction/synthesis internals with live LLM calls and keep the same typed contracts, retrieval tools, guardrails, and traces.

## Updated: Logging, Dedicated Ingestion Endpoint, Efficient LLM Usage

### Start DB

```bash
docker compose up -d postgres
```

### Load evidence into PostgreSQL

```bash
uvicorn app.main:app --reload
curl -X POST "http://localhost:8000/ingest/load" \
  -H "Content-Type: application/json" \
  -d '{"data_dir":"data","truncate":true}'
```

The ingestion endpoint is deterministic and does **not** call the LLM. It normalizes Salesforce, Gong, pricing, policy, and synthetic Slack evidence into the `documents` table.

### Generate a brief

```bash
curl -X POST "http://localhost:8000/briefs/generate" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USR-5003","opportunity_id":"OPP-1003"}'
```


### Check Ruff And Mypy
```bash
ruff check app --fix
ruff format app
mypy app

```


### Enable live LLM calls

```bash
export OPENAI_API_KEY="..."
export LLM_MODE=live
export OPENAI_MODEL=gpt-4.1-mini
export OPENAI_CHEAP_MODEL=gpt-4.1-nano
```

### Enable LangSmith tracing

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT="cato-deal-intel"
```

### Logs

All stages emit JSON logs:

- workflow start/end
- permission checks
- evidence loading
- hybrid RAG retrieval
- tool execution
- LLM call and token usage
- approval routing
- brief generation

See `docs/DEEP_PLA_LOGGING_LLM_RAG.md` for the deep PLA explanation.

## Production Structure Update

This version separates HTTP endpoints, dependencies, repositories, and workflow logic:

```text
app/api/endpoints/       # FastAPI routers only
app/dependencies/        # Dependency injection providers
app/repositories/        # Repository Design Pattern and DB access
app/workflows/           # Orchestration/state flow
app/agents/              # LLM-backed agent contracts
app/rag/                 # Hybrid RAG loader/retriever
app/observability/       # structured logs and traces
```

Important endpoints:

```http
GET  /health
POST /ingest/load
POST /briefs/generate
```

The ingestion endpoint is intentionally deterministic and does not call the LLM. The model is only used after authorization, metadata filtering, and retrieval.

See `docs/PRODUCTION_DESIGN_PATTERNS.md` for the design-pattern explanation.
