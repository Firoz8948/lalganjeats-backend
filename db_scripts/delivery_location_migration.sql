-- Live GPS for delivery partners (getlocation module)
-- psql -U postgres -d lalganjeats -f db_scripts/delivery_location_migration.sql

ALTER TABLE delivery_profiles
    ADD COLUMN IF NOT EXISTS current_latitude NUMERIC(10, 7);

ALTER TABLE delivery_profiles
    ADD COLUMN IF NOT EXISTS current_longitude NUMERIC(10, 7);

ALTER TABLE delivery_profiles
    ADD COLUMN IF NOT EXISTS location_updated_at TIMESTAMPTZ;
