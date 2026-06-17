# Skill: LLM Debugging and Observability

Use LangSmith and local traces for every LLM phase:
- agent input/output
- retrieved evidence IDs
- prompt version
- model name
- token estimate
- latency
- validation errors
- approval routing decisions
- guardrail blocks

Environment:
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=cato-deal-intelligence

Additional debugging tools:
- OpenTelemetry for API spans
- structured JSON logs
- trace table in Postgres
- replayable JSONL artifacts
- golden evaluation fixtures for regression tests
