# PLA Phase — Product, Logic, Architecture

## Product intent
Build a Strategic Deal Intelligence Assistant for negotiation preparation. It turns fragmented GTM data into a grounded, auditable brief while keeping humans in the loop.

## Core risks
1. Permission leakage: denied sources must not be retrieved, summarized, cited, or hinted at.
2. Hallucination: every material claim needs source citation.
3. Unsafe recommendations: discounts, legal terms, and customer-facing concession language require approval.
4. LLM nondeterminism: use typed contracts, validation, deterministic tools, traces, and test fixtures.

## Architecture
FastAPI/CLI -> BriefWorkflow -> permission gate -> hybrid RAG -> specialized agents -> guardrails -> approval router -> persisted brief/traces.

## Agents
- Deal Context Agent: deterministic CRM/account snapshot.
- Conversation Intelligence Agent: LLM extraction over allowed Gong/Slack evidence.
- Stakeholder Map Agent: buying committee and missing roles.
- Negotiation Strategy Agent: next actions and approval flags.

## Hybrid RAG emphasis
Production uses PostgreSQL + pgvector:
- vector similarity over embeddings
- full text keyword search over tsvector
- metadata filtering before scoring
- reranking by source reliability, recency, and citation coverage

## Debugging
Use LangSmith for LLM traces and local trace JSONL for offline review. For production, add OpenTelemetry spans and dashboards.
