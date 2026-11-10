"""Run Agency OS schema migrations in order, transactionally, on an explicitly chosen DB.

This script is intentionally never called by the production startup script.
Run it manually against a disposable/staging database after reviewing the target URL.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

MIGRATIONS = (
    "002_agency_os_foundation.sql",
    "003_secure_tenant_foundation.sql",
)
LOCK_KEY = 731904221


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required; no database was contacted.")

    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    connection = psycopg2.connect(database_url, connect_timeout=10)
    try:
        connection.autocommit = False
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("select pg_advisory_lock(%s)", (LOCK_KEY,))
            cursor.execute("""
                create table if not exists public.agency_os_schema_migrations (
                    version text primary key,
                    sha256 text not null,
                    applied_at timestamptz not null default now()
                )
            """)
        connection.commit()

        for filename in MIGRATIONS:
            path = migrations_dir / filename
            if not path.is_file():
                raise RuntimeError(f"Required migration is missing: {path}")
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "select sha256 from public.agency_os_schema_migrations where version = %s",
                    (filename,),
                )
                existing = cursor.fetchone()

            if existing:
                if existing["sha256"] != checksum:
                    raise RuntimeError(
                        f"{filename} has changed after being applied. Create a new migration; do not rewrite history."
                    )
                print(f"Already applied: {filename}")
                continue

            print(f"Applying: {filename}")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    cursor.execute(
                        "insert into public.agency_os_schema_migrations (version, sha256) values (%s, %s)",
                        (filename, checksum),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        print("Agency OS migrations are current.")
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    run()
