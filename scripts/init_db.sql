-- ─────────────────────────────────────────────────────────────────
--  Enterprise RAG Platform — Database Schema
--  Auto-run by PostgreSQL on first startup via Docker entrypoint
-- ─────────────────────────────────────────────────────────────────

-- ── Paper metadata ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,       -- ArXiv paper ID e.g. "1706.03762"
    title           TEXT NOT NULL,
    authors         TEXT[],
    abstract        TEXT,
    category        TEXT,                   -- e.g. "cs.AI"
    published_date  DATE,
    citation_count  INTEGER DEFAULT 0,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    embedding_model TEXT NOT NULL           -- track which model was used
);

-- ── Ingestion tracking (idempotency) ──────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    papers_processed INTEGER DEFAULT 0,
    chunks_created  INTEGER DEFAULT 0,
    embedding_model TEXT,
    config          JSONB                   -- store chunk_size, overlap etc.
);

-- ── Conversations ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    trace_id        TEXT PRIMARY KEY,       -- Langfuse trace ID
    user_id         TEXT,
    query           TEXT NOT NULL,
    mode            TEXT DEFAULT 'rag',     -- 'rag' or 'agent'
    response        TEXT,
    citations       JSONB,
    latency_ms      INTEGER,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    cost_usd        NUMERIC(10, 6),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── User feedback ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id              SERIAL PRIMARY KEY,
    trace_id        TEXT REFERENCES conversations(trace_id),
    rating          SMALLINT CHECK (rating IN (-1, 1)),  -- -1 = thumbs down, 1 = up
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Guardrail audit log ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guardrail_events (
    id              SERIAL PRIMARY KEY,
    trace_id        TEXT,
    stage           TEXT NOT NULL,          -- 'input' or 'output'
    guardrail_name  TEXT NOT NULL,          -- 'topic_filter', 'pii', 'faithfulness' etc.
    decision        TEXT NOT NULL,          -- 'PASS', 'BLOCK', 'WARN'
    reason_code     TEXT,                   -- 'OFF_TOPIC', 'PII_DETECTED' etc.
    confidence      NUMERIC(4, 3),
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Evaluation runs ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_runs (
    id                  SERIAL PRIMARY KEY,
    config_version      TEXT NOT NULL,      -- prompt version + model config
    faithfulness        NUMERIC(4, 3),
    answer_relevance    NUMERIC(4, 3),
    context_precision   NUMERIC(4, 3),
    context_recall      NUMERIC(4, 3),
    questions_tested    INTEGER,
    passed_regression   BOOLEAN,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Rate limiting (Redis handles this — table for analytics only) ─
CREATE TABLE IF NOT EXISTS rate_limit_events (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT,
    reason          TEXT,                   -- 'rpm_exceeded', 'daily_tokens_exceeded'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_conversations_user    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guardrail_trace       ON guardrail_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_decision    ON guardrail_events(decision);
CREATE INDEX IF NOT EXISTS idx_eval_runs_created     ON eval_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_category       ON papers(category);
CREATE INDEX IF NOT EXISTS idx_papers_date           ON papers(published_date DESC);
