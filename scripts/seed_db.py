"""
seed_db.py — Milestone 1, Step 2

Loads synthetic test data from database/seed.sql into the database.
Also hashes the placeholder passwords in the Users table using bcrypt.

Run after init_db.py:
    python scripts/seed_db.py
"""

import logging
import os
import sys

import psycopg2
from passlib.context import CryptContext

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "seed.sql")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Map email → plain-text password for seeding only; never use real passwords here.
SEED_PASSWORDS: dict[str, str] = {
    "admin@cinebook.com":  "AdminPass!23",
    "alice@example.com":   "password123",
    "bob@example.com":     "password123",
    "carol@example.com":   "password123",
    "david@example.com":   "password123",
    "eva@example.com":     "password123",
    "frank@example.com":   "password123",
    "grace@example.com":   "password123",
    "henry@example.com":   "password123",
    "isabel@example.com":  "password123",
}


def load_seed_sql(conn: psycopg2.extensions.connection) -> None:
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        seed_sql = f.read()

    with conn.cursor() as cur:
        cur.execute(seed_sql)
    conn.commit()
    logger.info("seed.sql applied.")


def hash_seed_passwords(conn: psycopg2.extensions.connection) -> None:
    """Replace placeholder hashes with real bcrypt hashes."""
    with conn.cursor() as cur:
        for email, plain in SEED_PASSWORDS.items():
            hashed = pwd_context.hash(plain)
            cur.execute(
                "UPDATE Users SET Password = %s WHERE Email = %s",
                (hashed, email),
            )
    conn.commit()
    logger.info("Seed passwords hashed with bcrypt.")


def check_already_seeded(conn: psycopg2.extensions.connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM Users")
        count = cur.fetchone()[0]
    return count > 0


def main() -> None:
    logger.info("=== CineBook — Seed Data Loader ===")

    conn = psycopg2.connect(settings.db_dsn)
    try:
        if check_already_seeded(conn):
            logger.warning(
                "Users table is not empty. Skipping seed to avoid duplicates. "
                "Truncate tables manually if you want a fresh seed."
            )
        else:
            load_seed_sql(conn)
            hash_seed_passwords(conn)
            logger.info("=== Seeding complete. ===")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
