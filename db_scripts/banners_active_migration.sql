-- Home banner slides: active flag + timestamps
-- psql -U postgres -d lalganjeats -f db_scripts/banners_active_migration.sql

ALTER TABLE home_banner_slides
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE home_banner_slides
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
