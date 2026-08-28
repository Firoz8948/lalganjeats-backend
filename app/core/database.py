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

        # orders table
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS otp VARCHAR(10);",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cash_collected NUMERIC(10,2) DEFAULT 0;",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS online_collected NUMERIC(10,2) DEFAULT 0;",
    ]
    try:
        with engine.begin() as conn:
            for stmt in statements:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
    except Exception as e:
        print(f"[AutoMigration] Notice: {e}")
