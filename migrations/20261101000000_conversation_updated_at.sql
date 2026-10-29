ALTER TABLE agent_conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON agent_conversations(user_id, updated_at DESC);

