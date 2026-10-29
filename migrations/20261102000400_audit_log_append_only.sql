-- tool_audit_logs is append-only. Two exceptions:
--  * foreign-key cleanup may NULL user_id / conversation_id (ON DELETE SET NULL when a guest or chat is deleted)
--  * the retention job may DELETE old rows by setting nexusagent.audit_retention = 'on' for its transaction
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

CREATE INDEX IF NOT EXISTS idx_tool_audit_logs_executed_at ON tool_audit_logs(executed_at);
