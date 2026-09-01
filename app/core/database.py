# backend/app/core/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_auto_migrations():
    """Apply missing database columns automatically on startup."""
    statements = [
        # users table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(80);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token TEXT;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS legal_terms_version VARCHAR(20);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS legal_terms_accepted_at TIMESTAMPTZ;",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username) WHERE username IS NOT NULL;",

        # delivery_profiles table
        "ALTER TABLE delivery_profiles ADD COLUMN IF NOT EXISTS current_lat DOUBLE PRECISION;",
        "ALTER TABLE delivery_profiles ADD COLUMN IF NOT EXISTS current_lng DOUBLE PRECISION;",
        "ALTER TABLE delivery_profiles ADD COLUMN IF NOT EXISTS last_location_update TIMESTAMPTZ;",
        "ALTER TABLE delivery_profiles ADD COLUMN IF NOT EXISTS has_location BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE delivery_profiles ADD COLUMN IF NOT EXISTS location_name VARCHAR(100);",

        # restaurants table
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS business_category_id INT;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS slug VARCHAR(120);",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS banner_mobile_url TEXT;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS list_banner_url TEXT;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS banner_url TEXT;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS logo_url TEXT;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS opening_time VARCHAR(20);",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS closing_time VARCHAR(20);",

        # orders table
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS otp VARCHAR(10);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_otp VARCHAR(10);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_otp_expires_at TIMESTAMPTZ;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_otp_verified_at TIMESTAMPTZ;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS distance_km DOUBLE PRECISION;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS eta_minutes INT;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes TEXT;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cash_collected NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS online_collected NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payu_txnid VARCHAR(100);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payu_mihpayid VARCHAR(100);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS display_total NUMERIC(10,2);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS actual_total NUMERIC(10,2);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS platform_fee NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS admin_earning NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_partner_earning NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cash_remittance_id INT;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code_id INT;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code VARCHAR(50);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_percent_off NUMERIC(5,2);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_discount_type VARCHAR(20);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_flat_off NUMERIC(10,2);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_free_delivery BOOLEAN DEFAULT FALSE;",

        # Doorstep online (UPI/QR at door) collection tracking via PayU.
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS collection_txnid VARCHAR(64);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS collection_amount NUMERIC(10,2);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS collection_initiated_at TIMESTAMPTZ;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS collection_online_paid_at TIMESTAMPTZ;",
        "CREATE INDEX IF NOT EXISTS ix_orders_collection_txnid ON orders(collection_txnid) WHERE collection_txnid IS NOT NULL;",

        # Promo audience (all vs new users) + usage tracked by mobile number.
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS audience VARCHAR(20) DEFAULT 'all';",
        "ALTER TABLE promo_code_usages ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(15);",
        "CREATE INDEX IF NOT EXISTS ix_promo_code_usages_customer_phone ON promo_code_usages(customer_phone);",
    ]
    for stmt in statements:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception:
            pass
