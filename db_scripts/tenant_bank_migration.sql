-- Tenant bank / settlement columns
-- psql … -f db_scripts/tenant_bank_migration.sql

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS bank_account_holder_name VARCHAR(150);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS bank_account_number VARCHAR(50);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS bank_ifsc_code VARCHAR(20);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS bank_name VARCHAR(150);
