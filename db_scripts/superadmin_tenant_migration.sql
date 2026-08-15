-- Multi-tenant + super admin layer
-- Run against existing DB: psql -U postgres -d lalganjeats -f db_scripts/superadmin_tenant_migration.sql

-- 1. Tenants
CREATE TABLE IF NOT EXISTS tenants (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(150) NOT NULL,
    slug                    VARCHAR(100) NOT NULL UNIQUE,
    admin_user_id           INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    center_latitude         NUMERIC(10, 7) NOT NULL,
    center_longitude        NUMERIC(10, 7) NOT NULL,
    center_address          TEXT NOT NULL,
    one_time_fee            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    platform_charge_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);

-- 2. Delivery zones
CREATE TABLE IF NOT EXISTS delivery_zones (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    radius_km    NUMERIC(8, 2) NOT NULL,
    pricing_type VARCHAR(20) NOT NULL,  -- flat | per_km
    rate         NUMERIC(10, 2) NOT NULL,
    sort_order   INTEGER DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ,
    CONSTRAINT uq_zone_tenant_name UNIQUE (tenant_id, name)
);

-- 3. users.tenant_id
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_tenant_id'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT fk_users_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);

-- 4. restaurants.tenant_id
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_restaurants_tenant_id'
    ) THEN
        ALTER TABLE restaurants
            ADD CONSTRAINT fk_restaurants_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_restaurants_tenant_id ON restaurants(tenant_id);

-- 5. Widen role check: admin + super_admin
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN (
        'customer',
        'restaurant_owner',
        'delivery_partner',
        'admin',
        'super_admin'
    ));

-- 6. Migrate previous platform operators → tenant admin
--    (seed_data.py will create the real super_admin account)
UPDATE users
SET role = 'admin'
WHERE role = 'super_admin'
  AND email IS DISTINCT FROM 'superadmin';
