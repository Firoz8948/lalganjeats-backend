-- Fixed platform charge collected from customers at checkout.
-- Safe to run more than once.

ALTER TABLE payment_settings
  ADD COLUMN IF NOT EXISTS platform_charge_rupees DOUBLE PRECISION NOT NULL DEFAULT 2.0;

UPDATE payment_settings
SET platform_charge_rupees = 2.0
WHERE platform_charge_rupees IS NULL;
