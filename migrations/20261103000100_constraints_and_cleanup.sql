-- ==============================================================================
-- R2-LOG-14: missing index and constraints, remove the dead hitl_approved column
-- Version: 20261103000100
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);

-- Orphan rows (no owner) are invisible to every query; remove them, then forbid them.
DELETE FROM agent_conversations WHERE user_id IS NULL;
ALTER TABLE agent_conversations ALTER COLUMN user_id SET NOT NULL;

DELETE FROM rate_limit_buckets WHERE user_id IS NULL;
ALTER TABLE rate_limit_buckets ALTER COLUMN user_id SET NOT NULL;

UPDATE rate_limit_buckets SET tokens_remaining = 0 WHERE tokens_remaining < 0;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'rate_limit_tokens_nonneg') THEN
        ALTER TABLE rate_limit_buckets
            ADD CONSTRAINT rate_limit_tokens_nonneg CHECK (tokens_remaining >= 0);
    END IF;
END
$$;

-- HITL was removed: the column is always TRUE. Rewrite the guard without it, then drop the column.
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

ALTER TABLE tool_audit_logs DROP COLUMN IF EXISTS hitl_approved;
