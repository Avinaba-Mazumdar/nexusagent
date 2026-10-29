ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64);
UPDATE document_chunks SET embedding_model = 'gemini-embedding-001'
WHERE embedding IS NOT NULL AND embedding_model IS NULL;
