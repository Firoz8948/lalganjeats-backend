-- Audited restaurant impersonation sessions.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS impersonation_sessions (
  id SERIAL PRIMARY KEY,
  jti VARCHAR(64) NOT NULL UNIQUE,
  admin_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
  purpose VARCHAR(40) NOT NULL DEFAULT 'restaurant_admin_impersonation',
  ip_address VARCHAR(64),
  user_agent TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_impersonation_sessions_admin
  ON impersonation_sessions (admin_user_id);
CREATE INDEX IF NOT EXISTS idx_impersonation_sessions_owner
  ON impersonation_sessions (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_impersonation_sessions_restaurant
  ON impersonation_sessions (restaurant_id);
CREATE INDEX IF NOT EXISTS idx_impersonation_sessions_tenant
  ON impersonation_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_impersonation_sessions_live
  ON impersonation_sessions (jti)
  WHERE ended_at IS NULL;
