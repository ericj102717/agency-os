#!/usr/bin/env python3
"""
SQLite to Postgres Migration Script
====================================
Copies all data from the local SQLite data.db to the configured Postgres
database (via DATABASE_URL). Run once on startup when DATABASE_URL is set
and the Postgres database is empty.

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING for
idempotency.
"""

import os
import sys
import sqlite3
import json

# Add the backend directory to the path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

DB_PATH = os.path.join(BACKEND_DIR, "data.db")

TABLES_TO_MIGRATE = [
    "business_config",
    "contacts",
    "opportunities",
    "revenue_records",
    "referral_sources",
    "import_batches",
    "import_issues",
    "services",
    "lead_sources",
    "sales_stages",
    "actions",
    "recommendations",
    "recommendation_feedback",
    "business_memory",
    "user_preferences",
    "demo_state",
]

# Column names that should be converted from SQLite INTEGER (0/1) to boolean
BOOLEAN_COLUMNS = {
    "contacts": ["email_consent", "sms_consent", "call_consent", "is_sample"],
    "business_config": ["setup_complete"],
    "services": ["is_active"],
    "lead_sources": ["is_active"],
    "sales_stages": ["is_closed", "is_won"],
    "user_preferences": ["demo_mode", "auto_refresh", "notif_new_leads", "notif_revenue_gap",
                         "notif_stuck_opps", "notif_referral_ops"],
}

def migrate():
    """Migrate data from SQLite to Postgres."""
    # Check if DATABASE_URL is set
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL not set — skipping migration")
        return False

    # Check if SQLite file exists
    if not os.path.exists(DB_PATH):
        print(f"SQLite file not found at {DB_PATH} — nothing to migrate")
        return False

    # Import db module
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("psycopg2 not installed — skipping migration")
        return False

    # Connect to SQLite (read-only)
    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to Postgres
    pg_conn = psycopg2.connect(database_url)
    pg_conn.autocommit = False
    pg_cursor = pg_conn.cursor()

    total_migrated = 0

    for table in TABLES_TO_MIGRATE:
        try:
            # Check if table has data in SQLite
            count_row = sqlite_conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            count = count_row["c"] if count_row else 0
            if count == 0:
                print(f"  {table}: no data in SQLite, skipping")
                continue

            # Check if Postgres already has data
            pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cursor.fetchone()[0]
            if pg_count > 0:
                print(f"  {table}: Postgres already has {pg_count} rows, skipping (use --force to overwrite)")
                continue

            # Get column names from SQLite
            cols_row = sqlite_conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = [r["name"] for r in cols_row if r]
            if not cols:
                # Try getting columns from first row
                first = sqlite_conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
                if first:
                    cols = list(first.keys())
                else:
                    print(f"  {table}: no columns found, skipping")
                    continue

            # Build INSERT statement with ON CONFLICT DO NOTHING
            col_list = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

            # Copy rows
            rows = sqlite_conn.execute(f"SELECT {col_list} FROM {table}").fetchall()
            batch = []
            for row in rows:
                values = [row[col] for col in cols]
                batch.append(values)

            if batch:
                pg_cursor.executemany(insert_sql, batch)
                migrated = pg_cursor.rowcount
                total_migrated += len(batch)
                print(f"  {table}: migrated {len(batch)} rows")
            else:
                print(f"  {table}: no rows to migrate")

        except Exception as e:
            print(f"  {table}: ERROR — {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

    print(f"\nMigration complete: {total_migrated} rows migrated to Postgres")
    return True

if __name__ == "__main__":
    print("Starting SQLite → Postgres migration...")
    migrate()
