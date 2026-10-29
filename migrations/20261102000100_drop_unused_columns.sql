-- Password auth was removed (Google OAuth + guest JWTs only); storage_path was never read.
ALTER TABLE users DROP COLUMN IF EXISTS hashed_password;
ALTER TABLE documents DROP COLUMN IF EXISTS storage_path;
