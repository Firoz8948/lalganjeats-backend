-- Admin-managed delivery partner identity and optional private documents.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS delivery_partner_details (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
  date_of_birth DATE NOT NULL,
  address TEXT NOT NULL,
  emergency_contact_name VARCHAR(100),
  emergency_contact_phone VARCHAR(15),
  joining_date DATE NOT NULL DEFAULT CURRENT_DATE,
  registered_vehicle_number VARCHAR(24) NOT NULL,
  bike_info TEXT NOT NULL,
  selfie_url TEXT NOT NULL,
  rc_document_key TEXT,
  aadhaar_document_key TEXT,
  pan_document_key TEXT,
  bank_passbook_document_key TEXT,
  bank_name VARCHAR(150),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_delivery_partner_vehicle_number
    UNIQUE (registered_vehicle_number)
);

CREATE INDEX IF NOT EXISTS idx_delivery_partner_details_user
  ON delivery_partner_details (user_id);
