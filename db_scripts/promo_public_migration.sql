-- Public vs secret promocodes for checkout offers list.
-- Safe to run more than once.

ALTER TABLE promo_codes
  ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_promo_codes_public_active
  ON promo_codes (is_public, is_active)
  WHERE is_public = TRUE AND is_active = TRUE;
