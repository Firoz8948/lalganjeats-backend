-- Audits email and WhatsApp delivery of aggregate partner reports.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS report_deliveries (
  id SERIAL PRIMARY KEY,
  tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
  admin_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_type VARCHAR(30) NOT NULL,
  target_id INTEGER NOT NULL,
  target_name VARCHAR(150) NOT NULL,
  period VARCHAR(20) NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  channel VARCHAR(20) NOT NULL,
  recipient VARCHAR(200) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_report_deliveries_tenant
  ON report_deliveries (tenant_id);
CREATE INDEX IF NOT EXISTS idx_report_deliveries_admin
  ON report_deliveries (admin_user_id);
CREATE INDEX IF NOT EXISTS idx_report_deliveries_target
  ON report_deliveries (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_report_deliveries_created
  ON report_deliveries (created_at DESC);
