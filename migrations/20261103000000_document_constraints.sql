-- ==============================================================================
-- R2-SEC-07: a user cannot store the same file twice
-- Version: 20261103000000
-- ==============================================================================

-- Keep the oldest copy of any existing duplicate (chunks cascade).
DELETE FROM documents d
USING documents d2
WHERE d.user_id = d2.user_id
  AND d.sha256_hash = d2.sha256_hash
  AND (d.uploaded_at > d2.uploaded_at OR (d.uploaded_at = d2.uploaded_at AND d.id > d2.id));

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_hash
    ON documents(user_id, sha256_hash)
    WHERE user_id IS NOT NULL;
