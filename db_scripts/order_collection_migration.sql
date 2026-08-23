-- COD / doorstep collection amounts (delivery partner)
-- psql "$DATABASE_URL" -f db_scripts/order_collection_migration.sql

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS cash_collected NUMERIC(10, 2);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS online_collected NUMERIC(10, 2);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS delivery_otp_verified_at TIMESTAMPTZ;
