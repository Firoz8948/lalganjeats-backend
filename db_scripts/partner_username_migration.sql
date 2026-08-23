-- Partner login username (password_hash already on users)
-- psql "$DATABASE_URL" -f db_scripts/partner_username_migration.sql

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS username VARCHAR(80);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username
    ON users (username)
    WHERE username IS NOT NULL;
