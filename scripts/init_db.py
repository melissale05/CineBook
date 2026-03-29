"""
init_db.py — Milestone 1, Step 1

Creates the cinebook database (if it doesn't exist) and applies schema.sql.

Run once per environment:
    python scripts/init_db.py
"""

import logging
import os
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")


def create_database_if_missing() -> None:
    """Connect to the postgres system DB and create cinebook if absent."""
    # Connect to the default 'postgres' database to issue CREATE DATABASE
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname="postgres",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.DB_NAME,)
        )
        if cur.fetchone() is None:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(settings.DB_NAME)
            ))
            logger.info("Database '%s' created.", settings.DB_NAME)
        else:
            logger.info("Database '%s' already exists — skipping creation.", settings.DB_NAME)

    conn.close()


def apply_schema() -> None:
    """Read schema.sql and execute it against the cinebook database."""
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = psycopg2.connect(settings.db_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        logger.info("Schema applied successfully.")
    except Exception:
        conn.rollback()
        logger.exception("Failed to apply schema.")
        raise
    finally:
        conn.close()


def main() -> None:
    logger.info("=== CineBook — Database Initialization ===")
    create_database_if_missing()
    apply_schema()
    logger.info("=== Initialization complete. ===")


if __name__ == "__main__":
    main()
