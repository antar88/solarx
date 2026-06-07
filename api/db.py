"""MySQL connection helpers for the API (read-only credentials)."""

from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
import pymysql.cursors

from api.config import Settings


@contextmanager
def get_connection(settings: Settings) -> Iterator[pymysql.connections.Connection]:
    """Yield a short-lived read-only DB connection, always closed afterwards."""
    conn = pymysql.connect(
        host=settings.db_host,
        user=settings.solarx_ro_db_user,
        password=settings.solarx_ro_db_password,
        database=settings.solarx_db,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        yield conn
    finally:
        conn.close()
