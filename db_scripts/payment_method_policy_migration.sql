-- Configurable prepaid/COD availability. Zone rate is used for partner earning.
-- Safe to run more than once.

ALTER TABLE payment_settings
  ADD COLUMN IF NOT EXISTS allow_prepaid_orders BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE payment_settings
  ADD COLUMN IF NOT EXISTS allow_cod_orders BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE payment_settings
  ADD COLUMN IF NOT EXISTS cod_max_order_amount DOUBLE PRECISION NOT NULL DEFAULT 500;
