-- Flat ₹ off + min cart value for promocodes
-- psql "$DATABASE_URL" -f db_scripts/promo_flat_min_cart_migration.sql

ALTER TABLE promo_codes
    ADD COLUMN IF NOT EXISTS discount_type VARCHAR(20) NOT NULL DEFAULT 'percent',
    ADD COLUMN IF NOT EXISTS flat_off NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS min_cart_value NUMERIC(10, 2);

UPDATE promo_codes
SET discount_type = 'percent'
WHERE discount_type IS NULL OR discount_type = '';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_promo_discount_type'
  ) THEN
    ALTER TABLE promo_codes
      ADD CONSTRAINT ck_promo_discount_type
      CHECK (discount_type IN ('percent', 'flat'));
  END IF;
END $$;

ALTER TABLE promo_code_usages
    ADD COLUMN IF NOT EXISTS discount_type_snapshot VARCHAR(20),
    ADD COLUMN IF NOT EXISTS flat_off_snapshot NUMERIC(10, 2);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS promo_discount_type VARCHAR(20),
    ADD COLUMN IF NOT EXISTS promo_flat_off NUMERIC(10, 2);
