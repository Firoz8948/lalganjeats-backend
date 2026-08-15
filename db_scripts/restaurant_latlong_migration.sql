-- Ensure restaurant coordinates exist (may already be in schema.sql)
-- psql -U postgres -d lalganjeats -f db_scripts/restaurant_latlong_migration.sql

ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS latitude NUMERIC(10, 8);

ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS longitude NUMERIC(11, 8);
