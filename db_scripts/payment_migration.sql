-- Payment split system migration
-- Run once against existing database

ALTER TABLE menu_items
  ADD COLUMN IF NOT EXISTS actual_price DECIMAL(10,2);

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS display_total DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS actual_total DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS platform_fee DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS admin_earning DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS razorpay_order_id VARCHAR(100),
  ADD COLUMN IF NOT EXISTS razorpay_payment_id VARCHAR(100);

ALTER TABLE order_items
  ADD COLUMN IF NOT EXISTS display_price DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS actual_price DECIMAL(10,2);

CREATE TABLE IF NOT EXISTS payment_settings (
  id INTEGER PRIMARY KEY DEFAULT 1,
  delivery_charge DOUBLE PRECISION DEFAULT 30.0,
  free_delivery_above DOUBLE PRECISION DEFAULT 299.0,
  delivery_boy_per_order_earning DOUBLE PRECISION DEFAULT 25.0,
  platform_fee_percent DOUBLE PRECISION DEFAULT 5.0,
  updated_at TIMESTAMPTZ
);

INSERT INTO payment_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS restaurant_earnings (
  id SERIAL PRIMARY KEY,
  restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
  order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
  display_price_total DOUBLE PRECISION NOT NULL,
  actual_price_total DOUBLE PRECISION NOT NULL,
  platform_fee DOUBLE PRECISION NOT NULL,
  amount_earned DOUBLE PRECISION NOT NULL,
  transfer_status VARCHAR(20) DEFAULT 'pending',
  razorpay_transfer_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS delivery_earnings (
  id SERIAL PRIMARY KEY,
  delivery_partner_id INTEGER NOT NULL REFERENCES users(id),
  order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
  amount_earned DOUBLE PRECISION NOT NULL,
  transfer_status VARCHAR(20) DEFAULT 'pending',
  razorpay_transfer_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS withdrawals (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  role VARCHAR NOT NULL,
  amount DOUBLE PRECISION NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  razorpay_payout_id TEXT,
  bank_account_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS bank_accounts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  role VARCHAR NOT NULL,
  account_holder_name VARCHAR NOT NULL,
  account_number VARCHAR NOT NULL,
  ifsc_code VARCHAR NOT NULL,
  razorpay_linked_account_id TEXT,
  razorpay_fund_account_id TEXT,
  is_verified BOOLEAN DEFAULT FALSE,
  is_primary BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
