-- NexusAgent schema (single source of truth). Applied by hand in the Neon SQL editor.
-- Fresh install: run this whole file.
-- Reset an existing database (DELETES ALL DATA): DROP SCHEMA public CASCADE; CREATE SCHEMA public; then run this file.
-- Make someone an admin (only way): UPDATE users SET is_admin = TRUE WHERE email = 'you@example.com';

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Users (guest JWTs and Google OAuth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255) NOT NULL DEFAULT 'Guest Reviewer',
    avatar_url TEXT,
    is_guest BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    client_ip VARCHAR(45),
    device_id VARCHAR(64),
    machine_hash VARCHAR(64),
    token_version INT NOT NULL DEFAULT 0,
    google_sub VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_device_id ON users(device_id);
CREATE INDEX IF NOT EXISTS idx_users_machine_hash ON users(machine_hash);
CREATE INDEX IF NOT EXISTS idx_users_client_ip ON users(client_ip);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL;

-- 2. Chat usage (rolling 24h quota)
-- One row per metered chat. Rolling 24h quota = count of rows newer than NOW() - 24h.
-- Buckets (app/core/quota_policy.py): per account/device, per guest network, service-wide guests,
-- service-wide total. Guest rows are the ones with a device_hash. client_ip holds an IPv4 address
-- or an IPv6 /64. machine_hash is no longer written (legacy column).
-- user_id is SET NULL (not CASCADE) so pruning a guest does not reset the device/IP counts.
CREATE TABLE IF NOT EXISTS chat_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    device_hash VARCHAR(64),
    machine_hash VARCHAR(64),
    client_ip VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_usage_user ON chat_usage(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_usage_device ON chat_usage(device_hash, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_usage_machine ON chat_usage(machine_hash, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_usage_ip ON chat_usage(client_ip, created_at);
-- The quota check scans the whole rolling day for the service-wide ceilings.
CREATE INDEX IF NOT EXISTS idx_chat_usage_created ON chat_usage(created_at);

-- 3. Document metadata
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    total_chunks INT NOT NULL DEFAULT 0,
    is_seeded BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_hash ON documents(sha256_hash);

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
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
            NEW.duration_ms, NEW.executed_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.tool_name, OLD.mcp_server, OLD.input_args, OLD.output_summary,
            OLD.duration_ms, OLD.executed_at)
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

-- 8. Gemini model cooldowns
-- One row per (router scope, model). A model whose retry_after is in the future is skipped until then.
-- scope: 'chat' (answers) or 'web_search' (search grounding, which has its own quota).
-- reason: rate_limited | unavailable | overloaded | timed_out. failure_count counts every recorded failure.
CREATE TABLE IF NOT EXISTS model_cooldowns (
    scope VARCHAR(32) NOT NULL,
    model VARCHAR(100) NOT NULL,
    reason VARCHAR(32) NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    failure_count INT NOT NULL DEFAULT 1,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    retry_after TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, model)
);

CREATE INDEX IF NOT EXISTS idx_model_cooldowns_retry_after ON model_cooldowns(retry_after);