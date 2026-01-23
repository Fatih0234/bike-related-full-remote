"""Database connection helpers."""

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg

from erp.config import Settings


def get_connection(settings: Optional[Settings] = None) -> psycopg.Connection:
    """Create a new database connection."""
    settings = settings or Settings()
    return psycopg.connect(settings.get_database_url())


@contextmanager
def db_cursor(settings: Optional[Settings] = None) -> Iterator[psycopg.Cursor]:
    """Yield a cursor with automatic commit/rollback."""
    conn = get_connection(settings)
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
