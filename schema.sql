-- Run this in PostgreSQL
-- psql -U postgres -d lalganjeats

-- ================================
-- USERS TABLE (single table, role-based)
-- Best approach — like Swiggy/Zomato
-- ================================
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(100),
    phone           VARCHAR(15) UNIQUE,
    email           VARCHAR(150) UNIQUE,
    password_hash   TEXT,                    -- NULL for OTP-only users
    role            VARCHAR(20) NOT NULL     -- 'customer' | 'restaurant_owner' | 'delivery_partner' | 'admin' | 'super_admin'
                    CHECK (role IN ('customer', 'restaurant_owner', 'delivery_partner', 'admin', 'super_admin')),
    is_active       BOOLEAN DEFAULT TRUE,
    is_verified     BOOLEAN DEFAULT FALSE,
    profile_image   TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- RESTAURANTS TABLE
-- ================================
CREATE TABLE restaurants (
    id              SERIAL PRIMARY KEY,
    owner_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    phone           VARCHAR(15),
    address         TEXT,
    city            VARCHAR(100) DEFAULT 'Lalganj',
    pincode         VARCHAR(10),
    latitude        DECIMAL(10, 8),
    longitude       DECIMAL(11, 8),
    logo_url        TEXT,
    is_open         BOOLEAN DEFAULT TRUE,
    is_approved     BOOLEAN DEFAULT FALSE,   -- Admin approves restaurant
    is_active       BOOLEAN DEFAULT TRUE,
    opening_time    TIME DEFAULT '08:00',
    closing_time    TIME DEFAULT '22:00',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- MENU CATEGORIES TABLE
-- ================================
CREATE TABLE menu_categories (
    id              SERIAL PRIMARY KEY,
    restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,   -- 'Biryani', 'Drinks', 'Desserts'
    sort_order      INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- MENU ITEMS TABLE (Swiggy/Zomato approach)
-- ================================
CREATE TABLE menu_items (
    id              SERIAL PRIMARY KEY,
    restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    category_id     INTEGER REFERENCES menu_categories(id) ON DELETE SET NULL,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    price           DECIMAL(10, 2) NOT NULL,
    original_price  DECIMAL(10, 2),          -- For showing strikethrough price
    is_veg          BOOLEAN DEFAULT TRUE,
    is_available    BOOLEAN DEFAULT TRUE,    -- Mark out of stock
    is_bestseller   BOOLEAN DEFAULT FALSE,
    image_url       TEXT,
    sort_order      INTEGER DEFAULT 0,
    is_deleted      BOOLEAN DEFAULT FALSE,   -- Soft delete
    deleted_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- ADDRESSES TABLE (Customer)
-- ================================
CREATE TABLE addresses (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label           VARCHAR(50) DEFAULT 'Home',  -- 'Home', 'Work', 'Other'
    full_address    TEXT NOT NULL,
    landmark        TEXT,
    city            VARCHAR(100) DEFAULT 'Lalganj',
    pincode         VARCHAR(10),
    latitude        DECIMAL(10, 8),
    longitude       DECIMAL(11, 8),
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- DELIVERY PARTNER PROFILES TABLE
-- ================================
CREATE TABLE delivery_profiles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    vehicle_type    VARCHAR(50),             -- 'bike', 'bicycle', 'scooter'
    vehicle_number  VARCHAR(20),
    license_number  VARCHAR(50),
    is_online       BOOLEAN DEFAULT FALSE,   -- Toggle online/offline
    total_earnings  DECIMAL(10, 2) DEFAULT 0,
    current_latitude   NUMERIC(10, 7),       -- live GPS (getlocation)
    current_longitude  NUMERIC(10, 7),
    location_updated_at TIMESTAMPTZ,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- ORDERS TABLE
-- ================================
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    order_number    VARCHAR(20) UNIQUE NOT NULL,  -- 'LE-2024-00001'
    customer_id     INTEGER NOT NULL REFERENCES users(id),
    restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
    delivery_partner_id INTEGER REFERENCES users(id),
    address_id      INTEGER REFERENCES addresses(id),
    status          VARCHAR(30) DEFAULT 'pending'
                    CHECK (status IN (
                        'pending', 'confirmed', 'preparing',
                        'ready_for_pickup', 'picked_up',
                        'on_the_way', 'delivered', 'cancelled'
                    )),
    payment_method  VARCHAR(20) DEFAULT 'cash'
                    CHECK (payment_method IN ('cash', 'upi')),
    payment_status  VARCHAR(20) DEFAULT 'pending'
                    CHECK (payment_status IN ('pending', 'paid', 'failed', 'refunded')),
    subtotal        DECIMAL(10, 2) NOT NULL,
    delivery_fee    DECIMAL(10, 2) DEFAULT 0,
    discount        DECIMAL(10, 2) DEFAULT 0,
    total_amount    DECIMAL(10, 2) NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- ORDER ITEMS TABLE
-- ================================
CREATE TABLE order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id    INTEGER NOT NULL REFERENCES menu_items(id),
    name            VARCHAR(150) NOT NULL,   -- Snapshot at time of order
    price           DECIMAL(10, 2) NOT NULL, -- Snapshot at time of order
    quantity        INTEGER NOT NULL DEFAULT 1,
    subtotal        DECIMAL(10, 2) NOT NULL
);

-- ================================
-- OTP TABLE
-- ================================
CREATE TABLE otps (
    id              SERIAL PRIMARY KEY,
    phone           VARCHAR(15) NOT NULL,
    otp_code        VARCHAR(6) NOT NULL,
    purpose         VARCHAR(30) DEFAULT 'login',  -- 'login' | 'register'
    is_used         BOOLEAN DEFAULT FALSE,
    expires_at      TIMESTAMP NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ================================
-- INDEXES (Performance)
-- ================================
CREATE INDEX idx_users_phone       ON users(phone);
CREATE INDEX idx_users_email       ON users(email);
CREATE INDEX idx_users_role        ON users(role);
CREATE INDEX idx_menu_restaurant   ON menu_items(restaurant_id, is_available, is_deleted);
CREATE INDEX idx_menu_category     ON menu_items(category_id);
CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_restaurant ON orders(restaurant_id);
CREATE INDEX idx_orders_delivery   ON orders(delivery_partner_id);
CREATE INDEX idx_orders_status     ON orders(status);
CREATE INDEX idx_otps_phone        ON otps(phone, is_used);

-- ================================
-- TENANTS (multi-tenant) + delivery zones
-- Full DDL also in db_scripts/superadmin_tenant_migration.sql
-- ================================
CREATE TABLE IF NOT EXISTS tenants (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(150) NOT NULL,
    slug                    VARCHAR(100) NOT NULL UNIQUE,
    admin_user_id           INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    center_latitude         NUMERIC(10, 7) NOT NULL,
    center_longitude        NUMERIC(10, 7) NOT NULL,
    center_address          TEXT NOT NULL,
    one_time_fee            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    platform_charge_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS delivery_zones (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    radius_km    NUMERIC(8, 2) NOT NULL,
    pricing_type VARCHAR(20) NOT NULL,
    rate         NUMERIC(10, 2) NOT NULL,
    sort_order   INTEGER DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ,
    CONSTRAINT uq_zone_tenant_name UNIQUE (tenant_id, name)
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL;
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL;

-- ================================
-- SEED: run python -m scripts.seed_data for real hashes
-- Platform: superadmin / Tenant: admin
-- ================================
