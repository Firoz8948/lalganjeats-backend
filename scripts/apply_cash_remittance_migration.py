"""Apply cash remittance migration against the app DATABASE_URL."""
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import settings

sql_path = Path("db_scripts/cash_remittance_migration.sql")
if not sql_path.exists():
    sql_path = Path("/app/db_scripts/cash_remittance_migration.sql")

raw = sql_path.read_text(encoding="utf-8")
cleaned = "\n".join(
    line for line in raw.splitlines() if not line.strip().startswith("--")
)
statements = [s.strip() for s in cleaned.split(";") if s.strip()]

engine = create_engine(settings.DATABASE_URL)
with engine.begin() as conn:
    for stmt in statements:
        conn.execute(text(stmt))
    exists = conn.execute(text("SELECT to_regclass('public.cash_remittances')")).scalar()
    col = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='orders' AND column_name='cash_remittance_id'"
        )
    ).scalar()

print("migration_ok", bool(exists), bool(col))
