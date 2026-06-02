from psycopg2 import pool
from core.config import settings

# Thread-safe connection pool — reuses connections instead of
# opening a new one per request
_pool = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=settings.database_url,
)


def get_conn():
    """Get a connection from the pool."""
    return _pool.getconn()


def release_conn(conn):
    """Return a connection to the pool."""
    _pool.putconn(conn)


def execute_query(sql: str, params=None, fetch: str = "all"):
    """
    Run a query and return results.
    fetch: 'all' | 'one' | 'none'
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "all":
                return cur.fetchall()
            elif fetch == "one":
                return cur.fetchone()
            conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def execute_write(sql: str, params=None):
    """Run an INSERT/UPDATE/DELETE."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)