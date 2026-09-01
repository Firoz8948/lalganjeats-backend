-- Promo audience (all users vs new users) + usage by mobile number.
-- Auto-runs on backend startup; this file is the documented fallback.

ALTER TABLE promo_codes
    ADD COLUMN IF NOT EXISTS audience VARCHAR(20) DEFAULT 'all';

ALTER TABLE promo_code_usages
    ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(15);

CREATE INDEX IF NOT EXISTS ix_promo_code_usages_customer_phone
    ON promo_code_usages(customer_phone);
