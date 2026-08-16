-- Small custom delivery islands outside normal tenant zone rings.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS delivery_exceptions (
  id SERIAL PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  latitude NUMERIC(10, 7) NOT NULL,
  longitude NUMERIC(10, 7) NOT NULL,
  radius_meters INTEGER NOT NULL DEFAULT 500,
  delivery_charge NUMERIC(10, 2) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_delivery_exception_tenant_name UNIQUE (tenant_id, name),
  CONSTRAINT ck_delivery_exception_radius CHECK (radius_meters >= 50)
);

CREATE INDEX IF NOT EXISTS idx_delivery_exceptions_tenant
  ON delivery_exceptions (tenant_id);
