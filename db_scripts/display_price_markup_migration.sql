-- Configurable display-price markup over seller transfer price
-- Safe to run more than once.

ALTER TABLE payment_settings
  ADD COLUMN IF NOT EXISTS display_price_markup_percent DOUBLE PRECISION DEFAULT 30.0;

UPDATE payment_settings
SET display_price_markup_percent = 30.0
WHERE display_price_markup_percent IS NULL;
