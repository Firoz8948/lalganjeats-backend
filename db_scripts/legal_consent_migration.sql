-- Versioned acceptance of customer and partner legal policies.
-- Safe to run more than once.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS legal_terms_version VARCHAR(20);

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS legal_terms_accepted_at TIMESTAMPTZ;
