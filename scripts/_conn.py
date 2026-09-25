"""
Shared connection handling for the scripts in this folder.

Two ways to point them at a database:

  1. Discrete settings in .env  (PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD)
     — the local development path.

  2. A single DATABASE_URL, e.g. the connection string Neon or Supabase hands
     you. When it is set it wins, and the scripts switch to "hosted" behaviour:
     they will not try to DROP and CREATE the database, because a managed
     provider gives you one already and usually will not let you drop it.

Import `connect()` rather than calling psycopg2 directly, so every script
behaves the same way against both.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def database_url() -> str | None:
    """The hosted connection string, if one is configured."""
    return os.getenv("DATABASE_URL") or None


def is_hosted() -> bool:
    return database_url() is not None


def settings() -> dict[str, str]:
    """Resolved connection settings, whichever way they were supplied."""
    dsn = database_url()
    if dsn:
        u = urlparse(dsn)
        return {
            "host": u.hostname or "localhost",
            "port": str(u.port or 5432),
            "dbname": (u.path or "/postgres").lstrip("/") or "postgres",
            "user": u.username or "postgres",
            "password": u.password or "",
            # Managed Postgres is TLS-only; locally 'prefer' keeps things simple.
            "sslmode": os.getenv("PGSSLMODE", "require"),
        }
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": os.getenv("PGPORT", "5432"),
        "dbname": os.getenv("PGDATABASE", "space_deploy"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
        "sslmode": os.getenv("PGSSLMODE", "prefer"),
    }


def connect(dbname: str | None = None, user: str | None = None,
            password: str | None = None, **kw):
    """
    Open a connection. Any of dbname/user/password can be overridden, which is
    how the telemetry generator connects as the ai_router role rather than as
    the owner.
    """
    cfg = settings()
    if dbname:
        cfg["dbname"] = dbname
    if user:
        cfg["user"] = user
    if password is not None:
        cfg["password"] = password
    cfg.update(kw)
    return psycopg2.connect(**cfg)


def describe() -> str:
    cfg = settings()
    where = "hosted" if is_hosted() else "local"
    return f"{cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['dbname']}  ({where})"
