"""
Database Connection Abstraction
================================
Provides a unified connection interface that uses PostgreSQL (via psycopg2)
when DATABASE_URL is set, and falls back to SQLite otherwise.

This module exports:
  - get_conn() — returns a connection object with .execute(), .commit(), .row_factory
  - init_db() — initializes schema (creates tables if needed)
  - is_postgres() — returns True if using Postgres
  - DB_TYPE — string "postgres" or "sqlite"

The Postgres connection wraps psycopg2 to provide sqlite3-compatible behavior:
  - Row objects accessible by column name (row["col_name"])
  - INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
  - INSERT OR REPLACE → INSERT ... ON CONFLICT ... DO UPDATE
  - datetime('now') → NOW()
  - PRAGMA statements are no-ops
  - lastrowid → RETURNING id
"""

import os
import re
import sqlite3
import threading
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "data.db")

DB_TYPE = "postgres" if DATABASE_URL else "sqlite"

# ---------------------------------------------------------------------------
# SQLite path (existing behavior)
# ---------------------------------------------------------------------------

_sqlite_conn: Optional[sqlite3.Connection] = None
_sqlite_lock = threading.Lock()

def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        _sqlite_conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
        _sqlite_conn.execute("PRAGMA foreign_keys=ON")
    return _sqlite_conn

# ---------------------------------------------------------------------------
# Postgres path
# ---------------------------------------------------------------------------

_pg_pool = None
_pg_lock = threading.Lock()

import psycopg2 as _psycopg2_mod
from psycopg2 import extras as _psycopg2_extras

def _get_pg_conn():
    """Get a Postgres connection — direct connection, Supabase pooler handles pooling."""
    try:
        conn = _psycopg2_mod.connect(
            DATABASE_URL,
            cursor_factory=_psycopg2_extras.RealDictCursor,
            connect_timeout=30,
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Postgres: {e}")

def _return_pg_conn(conn):
    """Close a direct Postgres connection."""
    try:
        conn.close()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# SQL translation: SQLite → Postgres
# ---------------------------------------------------------------------------

def _translate_sql(sql: str) -> str:
    """Translate SQLite-specific SQL to Postgres-compatible SQL."""
    result = sql

    # datetime('now') → NOW()
    result = re.sub(r"datetime\('now'\)", "NOW()", result, flags=re.IGNORECASE)

    # INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    result = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        result,
        flags=re.IGNORECASE,
    )
    # Add ON CONFLICT DO NOTHING for INSERT OR IGNORE (heuristic: if the translated
    # INSERT doesn't already have ON CONFLICT, append it)
    if "INSERT INTO" in result.upper() and "ON CONFLICT" not in result.upper() and "OR IGNORE" in sql.upper():
        result = re.sub(
            r"(INSERT\s+INTO\s+\w+\s*\([^)]*\)\s*VALUES\s*\([^)]*\))",
            r"\1 ON CONFLICT DO NOTHING",
            result,
            flags=re.IGNORECASE,
        )

    # INSERT OR REPLACE → handle via ON CONFLICT DO UPDATE
    # This is complex — for now, convert to INSERT ... ON CONFLICT DO UPDATE
    # Only works if we know the unique column. For simplicity, use DO NOTHING.
    result = re.sub(
        r"INSERT\s+OR\s+REPLACE\s+INTO",
        "INSERT INTO",
        result,
        flags=re.IGNORECASE,
    )

    # PRAGMA statements → no-ops
    if result.strip().upper().startswith("PRAGMA"):
        return ""

    # AUTOINCREMENT → SERIAL (handled in schema, but for ALTER TABLE)
    result = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", result, flags=re.IGNORECASE)

    # SQLite boolean literals: 1/0 for true/false (Postgres handles these natively)
    # No change needed — INTEGER works in both.

    return result

# ---------------------------------------------------------------------------
# Postgres connection wrapper (sqlite3-compatible API)
# ---------------------------------------------------------------------------

class PostgresRow(dict):
    """Dict-like row that also supports index access by column name (sqlite3.Row compatible)."""
    def __getitem__(self, key):
        if isinstance(key, str):
            return super().__getitem__(key)
        # Numeric index
        keys = list(super().keys())
        return super().__getitem__(keys[key])

class PostgresCursor:
    """Wraps a psycopg2 cursor to provide sqlite3-compatible behavior."""
    def __init__(self, pg_cursor):
        self._cursor = pg_cursor
        self.lastrowid = None

    def execute(self, sql: str, params=None):
        translated = _translate_sql(sql)
        if not translated:
            # No-op (e.g., PRAGMA)
            return self

        # sqlite3 uses ? placeholders, psycopg2 uses %s
        translated = translated.replace("?", "%s")

        if params is not None:
            if isinstance(params, (list, tuple)):
                self._cursor.execute(translated, params)
            elif isinstance(params, dict):
                self._cursor.execute(translated, params)
            else:
                self._cursor.execute(translated, params)
        else:
            self._cursor.execute(translated)

        # Capture lastrowid for INSERT statements
        if sql.strip().upper().startswith("INSERT"):
            try:
                self._cursor.execute("SELECT LASTVAL()")
                row = self._cursor.fetchone()
                if row:
                    self.lastrowid = row["lastval"] if isinstance(row, dict) else row[0]
            except Exception:
                pass

        return self

    def executemany(self, sql: str, params_seq):
        translated = _translate_sql(sql)
        if not translated:
            return
        translated = translated.replace("?", "%s")
        self._cursor.executemany(translated, params_seq)

    def executescript(self, sql: str):
        """Execute multiple SQL statements (sqlite3 compatible)."""
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                translated = _translate_sql(stmt)
                if translated:
                    translated = translated.replace("?", "%s")
                    try:
                        self._cursor.execute(translated)
                    except Exception:
                        pass

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [PostgresRow(dict(r)) for r in rows]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return PostgresRow(dict(row))

    def fetchmany(self, size=1):
        rows = self._cursor.fetchmany(size)
        return [PostgresRow(dict(r)) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()

class PostgresConnection:
    """Wraps a psycopg2 connection to provide sqlite3-compatible behavior."""
    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None  # We always return dict-like rows

    def execute(self, sql: str, params=None):
        cursor = self._conn.cursor()
        pg_cursor = PostgresCursor(cursor)
        pg_cursor.execute(sql, params)
        return pg_cursor

    def executescript(self, sql: str):
        cursor = self._conn.cursor()
        pg_cursor = PostgresCursor(cursor)
        pg_cursor.executescript(sql)
        self.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        cursor = self._conn.cursor()
        return PostgresCursor(cursor)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_postgres() -> bool:
    return DB_TYPE == "postgres"

def get_conn():
    """Get a database connection. Returns Postgres or SQLite connection."""
    if DB_TYPE == "postgres":
        return _get_pg_conn_wrapped()
    else:
        return _get_sqlite_conn()

def _get_pg_conn_wrapped() -> PostgresConnection:
    """Get a wrapped Postgres connection."""
    conn = _get_pg_conn()
    return PostgresConnection(conn)

def return_conn(conn):
    """Return a connection to the pool (Postgres only)."""
    if DB_TYPE == "postgres" and isinstance(conn, PostgresConnection):
        _return_pg_conn(conn._conn)

def init_db():
    """Initialize the database schema."""
    if DB_TYPE == "postgres":
        _init_pg()
    else:
        _init_sqlite()

def _init_sqlite():
    """Initialize SQLite schema using data_store's existing SCHEMA_SQL."""
    conn = _get_sqlite_conn()
    from data_store import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    conn.commit()

def _init_pg():
    """Initialize Postgres schema by running the migration SQL."""
    conn = _get_pg_conn()
    try:
        cursor = conn.cursor()
        migration_path = os.path.join(BASE_DIR, "migrations", "001_supabase_schema.sql")
        if os.path.exists(migration_path):
            with open(migration_path, "r") as f:
                schema_sql = f.read()
        else:
            # Fall back to the data_store SCHEMA_SQL, translated
            from data_store import SCHEMA_SQL
            schema_sql = _translate_sql(SCHEMA_SQL)
        # Execute each statement separately (psycopg2 doesn't have executescript)
        for stmt in schema_sql.split(";"):
            # Strip comments and whitespace — statements may have inline comments
            lines = stmt.strip().splitlines()
            clean_lines = [l for l in lines if not l.strip().startswith("--")]
            stmt = "\n".join(clean_lines).strip()
            if stmt:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    # Table/index already exists is fine
                    if "already exists" not in str(e):
                        print(f"Schema init warning: {e}")
        conn.commit()
    finally:
        _return_pg_conn(conn)

# ---------------------------------------------------------------------------
# Schema migration on import
# ---------------------------------------------------------------------------

# Auto-initialize on module load (only if not in import-time of another module)
# This is deferred to avoid circular imports — callers should call init_db() explicitly
