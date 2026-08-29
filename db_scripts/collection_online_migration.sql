-- Doorstep online collection tracking (PayU-backed UPI/QR at the customer's door).
-- Adds columns to orders so we can:
--   1. remember the PayU txnid started by the delivery partner,
--   2. know how much was collected online, and
--   3. record when PayU confirmed the payment (drives the DP "unlock Confirm Delivered" gate).
--
-- Idempotent — safe to re-run.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS collection_txnid VARCHAR(64),
    ADD COLUMN IF NOT EXISTS collection_amount NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS collection_initiated_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS collection_online_paid_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS ix_orders_collection_txnid
    ON orders(collection_txnid)
    WHERE collection_txnid IS NOT NULL;
