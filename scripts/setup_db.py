#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- database bootstrap.

Drops and recreates the `space_deploy` database, then runs sql/01..05 in
order as the superuser. Safe to run as many times as you like.

06_indexes.sql is deliberately NOT applied here: the Index Benchmark page
applies it at runtime so the before/after comparison is live.

    python scripts/setup_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _conn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"

PGDATABASE = _conn.settings()["dbname"]

# Passwords for the three application roles, substituted into 05_roles.sql.
ROLE_PASSWORDS = {
    "__GROUND_OPERATOR_PASSWORD__": os.getenv("GROUND_OPERATOR_PASSWORD", "ground123"),
    "__STUDENT_ANALYST_PASSWORD__": os.getenv("STUDENT_ANALYST_PASSWORD", "student123"),
    "__AI_ROUTER_PASSWORD__": os.getenv("AI_ROUTER_PASSWORD", "router123"),
}

ORDERED_FILES = [
    "01_schema.sql",
    "02_seed.sql",
    "03_views.sql",
    "04_functions.sql",
    "05_roles.sql",
]


def admin_connection(dbname: str):
    return _conn.connect(dbname=dbname)


def recreate_database() -> None:
    """
    Drop and recreate the mission database from the `postgres` maintenance DB.

    Skipped against a managed host: providers hand you a database already and
    generally will not let you drop it. 01_schema.sql drops every table itself,
    so re-running is still clean either way.
    """
    if _conn.is_hosted():
        print(f"  hosted database {PGDATABASE!r} — reusing it (no DROP/CREATE)")
        return

    conn = admin_connection("postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            # Kick off anyone still connected (a stray Streamlit session, psql, ...)
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM   pg_stat_activity
                WHERE  datname = %s AND pid <> pg_backend_pid()
                """,
                (PGDATABASE,),
            )
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(PGDATABASE)))
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(PGDATABASE)))
        print(f"  recreated database {PGDATABASE!r}")
    finally:
        conn.close()


def read_sql(name: str) -> str:
    text = (SQL_DIR / name).read_text(encoding="utf-8")
    if name == "05_roles.sql":
        for placeholder, value in ROLE_PASSWORDS.items():
            # Doubling quotes keeps a password containing ' from breaking the literal.
            text = text.replace(placeholder, value.replace("'", "''"))
        # The database name is not ours to choose on a managed host.
        text = text.replace("__DATABASE__", PGDATABASE.replace('"', '""'))
    return text


def run_scripts() -> None:
    conn = admin_connection(PGDATABASE)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        for name in ORDERED_FILES:
            with conn.cursor() as cur:
                try:
                    cur.execute(read_sql(name))
                except psycopg2.Error as exc:
                    print(f"\n  FAILED in {name}:\n    {exc}", file=sys.stderr)
                    raise SystemExit(1)
                # 05_roles.sql ends with a verification SELECT
                if cur.description:
                    rows = cur.fetchall()
                    print(f"  {name}: ok ({len(rows)} grant rows)")
                else:
                    print(f"  {name}: ok")
    finally:
        conn.close()


def summarise() -> None:
    conn = admin_connection(PGDATABASE)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 'tables', count(*) FROM information_schema.tables
                  WHERE table_schema='public' AND table_type='BASE TABLE'
                UNION ALL
                SELECT 'views', count(*) FROM information_schema.views
                  WHERE table_schema='public'
                UNION ALL
                SELECT 'routines', count(*) FROM information_schema.routines
                  WHERE routine_schema='public'
                UNION ALL
                SELECT 'pods', count(*)::int FROM deployer_pod
                UNION ALL
                SELECT 'cubes', count(*)::int FROM satellite_cube
                UNION ALL
                SELECT 'routers', count(*)::int FROM comm_router
                UNION ALL
                SELECT 'passes', count(*)::int FROM ground_pass
                """
            )
            print("\n  contents:")
            for label, count in cur.fetchall():
                print(f"    {label:<10} {count}")
    finally:
        conn.close()


def main() -> None:
    print(f"SomaiyaSat Ground Control -- setup")
    print(f"  target {_conn.describe()}\n")
    try:
        recreate_database()
        run_scripts()
        summarise()
    except psycopg2.OperationalError as exc:
        print(f"\nCould not connect to PostgreSQL:\n  {exc}", file=sys.stderr)
        print("Check that the server is running and that .env is correct.", file=sys.stderr)
        raise SystemExit(1)

    print("\nDone. Next: python scripts/generate_telemetry.py")


if __name__ == "__main__":
    main()
