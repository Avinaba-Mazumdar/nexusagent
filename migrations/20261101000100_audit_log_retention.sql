ALTER TABLE tool_audit_logs DROP CONSTRAINT IF EXISTS tool_audit_logs_conversation_id_fkey;
ALTER TABLE tool_audit_logs ADD CONSTRAINT tool_audit_logs_conversation_id_fkey
    FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE SET NULL;

