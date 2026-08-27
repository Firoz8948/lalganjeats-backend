-- Cash remittance: delivery partner remits doorstep cash to platform via PayU
-- psql "$DATABASE_URL" -f db_scripts/cash_remittance_migration.sql

CREATE TABLE IF NOT EXISTS cash_remittances (
    id SERIAL PRIMARY KEY,
    delivery_partner_id INTEGER NOT NULL REFERENCES users(id),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payu_txnid VARCHAR(100),
    payu_mihpayid VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_cash_remittances_partner
    ON cash_remittances (delivery_partner_id);

CREATE INDEX IF NOT EXISTS ix_cash_remittances_status
    ON cash_remittances (status);

CREATE INDEX IF NOT EXISTS ix_cash_remittances_payu_txnid
    ON cash_remittances (payu_txnid);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS cash_remittance_id INTEGER
        REFERENCES cash_remittances(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_orders_cash_remittance_id
    ON orders (cash_remittance_id);
