-- 1. הפעלת הרחבות נדרשות
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;


CREATE TABLE IF NOT EXISTS access_permissions (
    user_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    allowed_account_ids TEXT[] NOT NULL, -- שונה ל-TEXT Array
    allowed_source_types TEXT[] NOT NULL, -- שונה ל-TEXT Array
    can_view_restricted_account BOOLEAN NOT NULL DEFAULT FALSE,
    can_view_sensitive_pricing BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    stage TEXT NOT NULL,
    type TEXT NOT NULL,
    acv NUMERIC NOT NULL,
    tcv NUMERIC NOT NULL,
    close_date TEXT NOT NULL,
    owner TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    restricted_access BOOLEAN NOT NULL DEFAULT FALSE
);

-- 2. טבלת מסמכים וראיות (RAG Layer)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    stable_source_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_type TEXT NOT NULL, -- 'gong', 'salesforce', 'slack', 'pricing_notes'
    opportunity_id TEXT,
    account_id TEXT,
    source_access_level TEXT NOT NULL DEFAULT 'standard', -- 'standard', 'restricted'
    sensitivity TEXT NOT NULL DEFAULT 'standard',
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536), -- מותאם ל-1536 ממדים
    search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- אינדקסים לטבלת המסמכים
CREATE INDEX IF NOT EXISTS idx_documents_opportunity_id ON documents(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_tsv ON documents USING GIN(search_tsv);
CREATE INDEX IF NOT EXISTS idx_documents_scope ON documents(opportunity_id, account_id, source_type, source_access_level);

-- שימוש באינדקס HNSW המודרני לחיפוש וקטורי (יעיל יותר מ-ivfflat לטבלאות דינמיות)
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops);


-- 3. טבלת אישורים אנושיים (Human-In-The-Loop)
CREATE TABLE IF NOT EXISTS approval_requests (
    id BIGSERIAL PRIMARY KEY,
    approval_id TEXT UNIQUE NOT NULL, -- מזהה ייחודי עסקי APR-XXXX
    recommendation_id TEXT NOT NULL,
    opportunity_id TEXT NOT NULL,
    action_text TEXT NOT NULL,
    approval_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending_approval', -- 'pending_approval', 'approved', 'rejected'
    requested_by TEXT NOT NULL,
    reviewer_id TEXT,
    decision_reason TEXT,
    citations JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

-- אינדקסים לאישורים
CREATE INDEX IF NOT EXISTS idx_approval_opportunity_id ON approval_requests(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);


-- 4. טבלת לוגים וטרייסינג של סוכנים (Observability)
CREATE TABLE IF NOT EXISTS trace_events (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'agent.start', 'llm.call', 'retrieval.fetch'
    actor TEXT NOT NULL,      -- 'NegotiationStrategyAgent', 'User'
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- אינדקסים לטרייסינג
CREATE INDEX IF NOT EXISTS idx_trace_run_id ON trace_events(run_id);
CREATE INDEX IF NOT EXISTS idx_trace_event_type ON trace_events(event_type);


-- 5. טבלת דו"חות מודיעין שנשמרו (State Persistence)
CREATE TABLE IF NOT EXISTS generated_briefs (
    id BIGSERIAL PRIMARY KEY,
    brief_id TEXT UNIQUE NOT NULL, -- מזהה ייחודי עסקי BRF-XXXX
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    opportunity_id TEXT NOT NULL,
    brief_json JSONB NOT NULL, -- מכיל את ה-StrategicDealBrief המלא
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- אינדקסים לדו"חות
CREATE INDEX IF NOT EXISTS idx_generated_briefs_run_id ON generated_briefs(run_id);
CREATE INDEX IF NOT EXISTS idx_generated_briefs_opportunity_id ON generated_briefs(opportunity_id);