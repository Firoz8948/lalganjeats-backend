-- Add auditable manual settlement fields to both partner earning ledgers.
-- Apply this migration before deploying the settlement API.

ALTER TABLE restaurant_earnings
    ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS settled_by INTEGER REFERENCES users(id);

ALTER TABLE delivery_earnings
    ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS settled_by INTEGER REFERENCES users(id);

CREATE INDEX IF NOT EXISTS ix_restaurant_earnings_unsettled
    ON restaurant_earnings (restaurant_id, transfer_status);

CREATE INDEX IF NOT EXISTS ix_delivery_earnings_unsettled
    ON delivery_earnings (delivery_partner_id, transfer_status);

-- Historical rows are intentionally not remapped automatically. Existing
-- "completed" rows may represent real Razorpay transfers. Review those rows
-- before changing them to "unsettled".
