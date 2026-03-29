"""
Database connection helpers.

Provides a context-manager for safe connection/cursor lifecycle.
Milestone 2 (FastAPI routes) will use get_db() as a dependency.
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras  # DictCursor

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> psycopg2.extensions.connection:
    """Return a new psycopg2 connection.  Caller is responsible for closing it."""
    return psycopg2.connect(settings.db_dsn)


@contextmanager
def get_db():
    """
    Context manager that yields a DictCursor and auto-commits or rolls back.

    Usage:
        with get_db() as cursor:
            cursor.execute("SELECT * FROM Users")
            rows = cursor.fetchall()
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Database error — transaction rolled back")
        raise
    finally:
        conn.close()
