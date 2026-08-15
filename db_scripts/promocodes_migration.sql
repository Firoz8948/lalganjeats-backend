-- Promocodes + order coupon columns
-- psql -U postgres -d lalganjeats -f db_scripts/promocodes_migration.sql

CREATE TABLE IF NOT EXISTS promo_codes (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    code            VARCHAR(40) NOT NULL,
    channel         VARCHAR(20) NOT NULL DEFAULT 'all',
    percent_off     NUMERIC(5, 2),
    free_delivery   BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ,
    max_uses        INTEGER NOT NULL DEFAULT 0,
    remaining_uses  INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT uq_promo_tenant_code UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS ix_promo_codes_code ON promo_codes(code);
CREATE INDEX IF NOT EXISTS ix_promo_codes_tenant_id ON promo_codes(tenant_id);

CREATE TABLE IF NOT EXISTS promo_code_usages (
    id                     SERIAL PRIMARY KEY,
    promo_code_id          INTEGER NOT NULL REFERENCES promo_codes(id) ON DELETE CASCADE,
    order_id               INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    user_id                INTEGER REFERENCES users(id) ON DELETE SET NULL,
    discount_amount        NUMERIC(10, 2) NOT NULL DEFAULT 0,
    percent_off_snapshot   NUMERIC(5, 2),
    free_delivery_applied  BOOLEAN DEFAULT FALSE,
    client_channel         VARCHAR(20) NOT NULL DEFAULT 'web',
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_promo_usages_promo ON promo_code_usages(promo_code_id);
CREATE INDEX IF NOT EXISTS ix_promo_usages_user ON promo_code_usages(user_id);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code_id INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code VARCHAR(40);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_percent_off NUMERIC(5, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_free_delivery BOOLEAN DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_orders_promo_code_id'
    ) THEN
        ALTER TABLE orders
            ADD CONSTRAINT fk_orders_promo_code_id
            FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_orders_promo_code_id ON orders(promo_code_id);
