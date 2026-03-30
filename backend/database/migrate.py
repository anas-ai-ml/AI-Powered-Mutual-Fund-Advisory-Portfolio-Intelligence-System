"""
backend/database/migrate.py
────────────────────────────
Safe incremental migration script.

Adds missing columns to existing tables and creates new tables introduced
after the initial schema deployment. Uses ADD COLUMN IF NOT EXISTS so it
is safe to run multiple times.

Usage:
    python -m backend.database.migrate
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from sqlalchemy import text
from backend.database.connection import engine
from backend.database.models import Base


def run():
    migrations = [
        # ── clients: columns added in v2 ──────────────────────────────────
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS occupation VARCHAR(255)",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS income_bracket VARCHAR(100)",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS investable_surplus FLOAT",

        # ── advisors: branding columns ────────────────────────────────────
        "ALTER TABLE advisors ADD COLUMN IF NOT EXISTS firm_name VARCHAR(255)",
        "ALTER TABLE advisors ADD COLUMN IF NOT EXISTS phone VARCHAR(50)",
        "ALTER TABLE advisors ADD COLUMN IF NOT EXISTS logo_path VARCHAR(500)",
    ]

    # Create any entirely new tables (advisor_overrides, etc.) that don't exist yet
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        for sql in migrations:
            print(f"  Running: {sql}")
            conn.execute(text(sql))
        conn.commit()

    print("\nMigration complete.")


if __name__ == "__main__":
    run()
