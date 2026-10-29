-- ==============================================================================
-- NexusAgent core schema
-- Target: Neon Serverless PostgreSQL 18 with pgvector and full-text tsvector
-- Version: 20260901000000
-- Squashed from the incremental migrations through 20261102000400.
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Users (guest JWTs and Google OAuth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255) NOT NULL DEFAULT 'Guest Reviewer',
    avatar_url TEXT,
    is_guest BOOLEAN NOT NULL DEFAULT TRUE,
    client_ip VARCHAR(45),
    device_id VARCHAR(64),
    token_version INT NOT NULL DEFAULT 0,
    google_sub VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_device_id ON users(device_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL;

-- 2. Token-bucket rate limiter, one row per user
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tokens_remaining INT NOT NULL DEFAULT 5,
    bucket_capacity INT NOT NULL DEFAULT 5,
    last_replenished_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rate_limit_buckets_user_id_key UNIQUE (user_id)
);

-- 3. Document metadata
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    total_chunks INT NOT NULL DEFAULT 0,
    is_seeded BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Document chunks with pgvector and tsvector
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    embedding_model VARCHAR(64),
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_search_vector
    ON document_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON document_chunks(document_id);

-- 5. Conversations
CREATE TABLE IF NOT EXISTS agent_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Architectural Inquiry',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_created ON agent_conversations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON agent_conversations(user_id, updated_at DESC);

-- 6. Messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    plan_trace JSONB,
    reflection_summary JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at ASC);

-- 7. Tool execution audit log (append-only)
CREATE TABLE IF NOT EXISTS tool_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES agent_conversations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tool_name VARCHAR(100) NOT NULL,
    mcp_server VARCHAR(100) NOT NULL DEFAULT 'nexusagent-internal',
    input_args JSONB NOT NULL,
    output_summary JSONB,
    duration_ms INT NOT NULL DEFAULT 0,
    hitl_approved BOOLEAN NOT NULL DEFAULT TRUE,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_logs_executed_at ON tool_audit_logs(executed_at);

-- Append-only, with two exceptions:
--  * foreign-key cleanup may NULL user_id / conversation_id
--  * the retention job may DELETE old rows by setting nexusagent.audit_retention = 'on'
CREATE OR REPLACE FUNCTION tool_audit_logs_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('nexusagent.audit_retention', true) = 'on' THEN
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE'
       AND (NEW.id, NEW.tool_name, NEW.mcp_server, NEW.input_args, NEW.output_summary,
            NEW.duration_ms, NEW.hitl_approved, NEW.executed_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.tool_name, OLD.mcp_server, OLD.input_args, OLD.output_summary,
            OLD.duration_ms, OLD.hitl_approved, OLD.executed_at)
       AND (NEW.user_id IS NULL OR NEW.user_id IS NOT DISTINCT FROM OLD.user_id)
       AND (NEW.conversation_id IS NULL OR NEW.conversation_id IS NOT DISTINCT FROM OLD.conversation_id)
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'tool_audit_logs is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tool_audit_logs_guard ON tool_audit_logs;
CREATE TRIGGER tool_audit_logs_guard
    BEFORE UPDATE OR DELETE ON tool_audit_logs
    FOR EACH ROW EXECUTE FUNCTION tool_audit_logs_guard();
