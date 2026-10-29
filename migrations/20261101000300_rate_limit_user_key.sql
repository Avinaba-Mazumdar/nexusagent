-- 20261101000300_rate_limit_user_key.sql
-- Consolidate duplicate rate_limit_buckets per user_id keeping the lowest tokens_remaining
DELETE FROM rate_limit_buckets r1
USING rate_limit_buckets r2
WHERE r1.user_id = r2.user_id
  AND (r1.tokens_remaining > r2.tokens_remaining
       OR (r1.tokens_remaining = r2.tokens_remaining AND r1.id > r2.id));

ALTER TABLE rate_limit_buckets DROP CONSTRAINT IF EXISTS unique_user_ip;
ALTER TABLE rate_limit_buckets ADD CONSTRAINT rate_limit_buckets_user_id_key UNIQUE (user_id);
ALTER TABLE rate_limit_buckets DROP COLUMN IF EXISTS client_ip;

