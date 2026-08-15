-- Order dispatch + tenant scoping columns
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_latitude NUMERIC(10, 7);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_longitude NUMERIC(10, 7);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS distance_km NUMERIC(8, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS eta_minutes INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_partner_earning NUMERIC(10, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_otp VARCHAR(6);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_otp_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_orders_tenant_id ON orders(tenant_id);

CREATE TABLE IF NOT EXISTS delivery_offers (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    delivery_partner_id INTEGER NOT NULL REFERENCES users(id),
    rank INTEGER NOT NULL,
    distance_km NUMERIC(8, 2),
    status VARCHAR(20) DEFAULT 'offered',
    offered_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    CONSTRAINT uq_offer_order_partner UNIQUE (order_id, delivery_partner_id)
);

CREATE INDEX IF NOT EXISTS ix_delivery_offers_order_id ON delivery_offers(order_id);
CREATE INDEX IF NOT EXISTS ix_delivery_offers_partner ON delivery_offers(delivery_partner_id);
