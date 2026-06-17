CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  stable_source_id TEXT NOT NULL,
  source_file TEXT NOT NULL,
  source_type TEXT NOT NULL,
  opportunity_id TEXT,
  account_id TEXT,
  source_access_level TEXT NOT NULL DEFAULT 'standard',
  sensitivity TEXT NOT NULL DEFAULT 'standard',
  content TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1536),
  search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_tsv ON documents USING GIN(search_tsv);
CREATE INDEX IF NOT EXISTS idx_documents_scope ON documents(opportunity_id, account_id, source_type, source_access_level);
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

CREATE TABLE IF NOT EXISTS briefs (
  id BIGSERIAL PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  requester_user_id TEXT NOT NULL,
  status TEXT NOT NULL,
  brief_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS approvals (
  id BIGSERIAL PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  recommendation_id TEXT NOT NULL,
  approval_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  rationale TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS traces (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
