"""SQLite connection and numbered SQL migrations (S1-2)."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(path=None):
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn):
    """Apply every migrations/NNN_*.sql not yet recorded. Returns names applied."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
    done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with conn:
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
        applied.append(path.name)
    return applied


_conn = None


def get_db():
    """FastAPI dependency: one shared connection, migrated on first use."""
    global _conn
    if _conn is None:
        _conn = connect()
        migrate(_conn)
    return _conn


def set_db(conn):
    """Use a specific connection (tests)."""
    global _conn
    _conn = conn


@contextmanager
def transaction(conn):
    with conn:
        yield conn
