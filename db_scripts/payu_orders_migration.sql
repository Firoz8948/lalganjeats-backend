-- PayU prepaid checkout fields on orders
-- psql "$DATABASE_URL" -f db_scripts/payu_orders_migration.sql

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS payu_txnid VARCHAR(100);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS payu_mihpayid VARCHAR(100);

CREATE INDEX IF NOT EXISTS ix_orders_payu_txnid ON orders (payu_txnid);
