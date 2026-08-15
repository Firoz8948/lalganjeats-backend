-- Run in PostgreSQL
-- psql -U postgres -d lalganjeats

CREATE TABLE IF NOT EXISTS customer_profiles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE
                    REFERENCES users(id) ON DELETE CASCADE,
    full_name       VARCHAR(100),
    email           VARCHAR(150),
    phone           VARCHAR(15),
    date_of_birth   DATE,
    gender          VARCHAR(10),
    profile_image   TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS addresses (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
    label           VARCHAR(50) DEFAULT 'Home',
    full_address    TEXT NOT NULL,
    landmark        VARCHAR(200),
    city            VARCHAR(100) DEFAULT 'Lalganj',
    pincode         VARCHAR(10),
    latitude        VARCHAR(20),
    longitude       VARCHAR(20),
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_settings (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL UNIQUE
                            REFERENCES users(id) ON DELETE CASCADE,
    notif_order_updates     BOOLEAN DEFAULT TRUE,
    notif_offers            BOOLEAN DEFAULT TRUE,
    notif_sms               BOOLEAN DEFAULT TRUE,
    preferred_language      VARCHAR(10) DEFAULT 'en',
    preferred_payment       VARCHAR(20) DEFAULT 'cash',
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_addresses_user
    ON addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_user
    ON customer_profiles(user_id);
