"""
Connection helper for the SomaiyaSat Ground Control dashboard.

The whole point of this module: Streamlit connects to PostgreSQL *as the role
the user logged in with*. There is no application-level permission check
anywhere in this project. If student_analyst cannot insert a telemetry packet,
that is PostgreSQL refusing it, and the error you see on screen is the server's
own message. Hiding the button would prove nothing.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.errors
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _setting(name: str, default: str = "") -> str:
    """
    Read one connection setting.

    Streamlit Community Cloud has no .env — it injects st.secrets instead — so
    secrets win where they exist and the local .env is the fallback. Reading
    st.secrets raises when no secrets file is configured at all, hence the
    guard.
    """
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


PGHOST = _setting("PGHOST", "localhost")
PGPORT = _setting("PGPORT", "5432")
PGDATABASE = _setting("PGDATABASE", "space_deploy")
# Managed Postgres (Neon, Supabase) is TLS-only; 'prefer' keeps local simple.
PGSSLMODE = _setting("PGSSLMODE", "prefer")

# The three application roles created by sql/05_roles.sql.
ROLES: dict[str, dict[str, str]] = {
    "ground_operator": {
        "label": "Ground Operator",
        "blurb": "Mission control. Full DML on every table plus EXECUTE on the "
                 "routines, so it can confirm deployments and run passes.",
        "env": "GROUND_OPERATOR_PASSWORD",
    },
    "student_analyst": {
        "label": "Student Analyst",
        "blurb": "Read-only coursework account. SELECT on the views and on "
                 "telemetry. Every INSERT / UPDATE / DELETE is refused by the server.",
        "env": "STUDENT_ANALYST_PASSWORD",
    },
    "ai_router": {
        "label": "AI Router (spacecraft)",
        "blurb": "The satellite's own account. INSERT on telemetry, SELECT on "
                 "comm_router and payload_priority, nothing else at all.",
        "env": "AI_ROUTER_PASSWORD",
    },
}

# page -> (SQL concept demonstrated, experiment / course outcome)
SIDEBAR_NOTES = {
    "home":       ("Three-way JOIN across pod -> cube -> router (v_mission_status)",
                   "Exp 6 - Views & Joins, CO3"),
    "deployment": ("TCL: one transaction per deployment, ROLLBACK on failure, "
                   "audit row written in a separate transaction",
                   "Exp 9 - TCL, CO1 & CO4"),
    "telemetry":  ("DML with filters + DCL: the INSERT below is allowed or "
                   "refused by PostgreSQL based on your role",
                   "Exp 4 - DML, CO1 / Exp 7 - DCL, CO2"),
    "health":     ("Aggregates with GROUP BY / HAVING and a CASE health flag "
                   "(v_cube_health, v_low_battery_cubes)",
                   "Exp 5 - Aggregates, CO2"),
    "planner":    ("PL/pgSQL function with a SUM() OVER (ORDER BY ...) window "
                   "function, then a SAVEPOINT-protected transaction",
                   "Exp 9 - TCL, CO4 / Exp 6 - CO3"),
    "benchmark":  ("B-tree indexes and EXPLAIN (ANALYZE) before vs after",
                   "Exp 8 - Indexing, CO3"),
}


# ---------------------------------------------------------------------------
# connection
# ---------------------------------------------------------------------------
def connect(role: str, password: str):
    """Open a connection AS `role`. Raises psycopg2.OperationalError on bad login."""
    return psycopg2.connect(
        host=PGHOST, port=PGPORT, dbname=PGDATABASE,
        user=role, password=password,
        sslmode=PGSSLMODE,
        connect_timeout=8,
        application_name=f"somaiyasat-ground-control/{role}",
    )


def is_logged_in() -> bool:
    return bool(st.session_state.get("role"))


def login(role: str, password: str) -> tuple[bool, str]:
    """Validate the credentials by actually connecting as that role."""
    try:
        conn = connect(role, password)
    except psycopg2.OperationalError as exc:
        return False, str(exc).strip()
    conn.close()
    st.session_state["role"] = role
    st.session_state["password"] = password
    return True, ""


def logout() -> None:
    conn = st.session_state.pop("conn", None)
    if conn is not None and not conn.closed:
        conn.close()
    st.session_state.pop("role", None)
    st.session_state.pop("password", None)


def get_conn():
    """The live connection for the logged-in role, reopened if it went stale."""
    if not is_logged_in():
        raise RuntimeError("not logged in")

    conn = st.session_state.get("conn")
    if conn is None or conn.closed:
        conn = connect(st.session_state["role"], st.session_state["password"])
        st.session_state["conn"] = conn
    else:
        # A previous statement may have failed and left the session aborted.
        if conn.status != psycopg2.extensions.STATUS_READY:
            conn.rollback()
    return conn


def require_login() -> None:
    """Guard placed at the top of every page."""
    if not is_logged_in():
        st.warning("Please log in on the **Home** page first.")
        st.stop()


# ---------------------------------------------------------------------------
# query helpers
# ---------------------------------------------------------------------------
def query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. Permission errors propagate."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return pd.DataFrame(rows, columns=cols)


def execute(sql: str, params: tuple | None = None, commit: bool = True):
    """Run a statement. Returns rowcount. Permission errors propagate."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            count = cur.rowcount
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return count


def scalar(sql: str, params: tuple | None = None):
    df = query(sql, params)
    return None if df.empty else df.iat[0, 0]


# ---------------------------------------------------------------------------
# the deployment transaction, driven from Python
# ---------------------------------------------------------------------------
def confirm_deployment(pod_id: str, simulate_failure: bool) -> tuple[bool, str]:
    """
    CALL confirm_deployment() as one transaction.

    On failure the procedure raises, so the whole transaction is rolled back and
    the pod/cube updates vanish. The audit row therefore CANNOT be written
    inside the procedure -- it would be rolled back too. Instead we roll back
    here and then write the log row in a FRESH transaction via
    log_deployment_attempt(). That is the bit the spec asks Python to get right.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CALL confirm_deployment(%s, %s)", (pod_id, simulate_failure))
        conn.commit()                      # <-- COMMIT
        return True, "Deployment confirmed and committed."

    except psycopg2.errors.InsufficientPrivilege as exc:
        conn.rollback()
        return False, f"PERMISSION DENIED -- {exc}"

    except psycopg2.Error as exc:
        conn.rollback()                    # <-- ROLLBACK: pod/cube untouched
        message = str(exc).strip()

        # Separate transaction, so this survives the rollback above.
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT log_deployment_attempt(%s, %s, %s)",
                    (pod_id, "CONFIRM_DEPLOYMENT (SIMULATED FAILURE)", "ROLLED_BACK"),
                )
            conn.commit()
        except psycopg2.Error:
            conn.rollback()                # analyst role cannot log; not fatal

        return False, message


# ---------------------------------------------------------------------------
# presentation helpers
# ---------------------------------------------------------------------------
def sidebar(page_key: str) -> None:
    """Role badge + the SQL concept this page demonstrates."""
    role = st.session_state.get("role")
    with st.sidebar:
        if role:
            st.markdown(f"**Connected as**  \n`{role}`")
            st.caption(ROLES[role]["blurb"])
            if st.button("Log out", width="stretch"):
                logout()
                st.rerun()
        st.divider()
        concept, exp = SIDEBAR_NOTES[page_key]
        st.markdown("**SQL concept on this page**")
        st.info(concept)
        st.caption(f"{exp}")


def friendly_error(exc: Exception) -> None:
    """Render a Postgres error the way a marker wants to see it."""
    if isinstance(exc, psycopg2.errors.InsufficientPrivilege):
        role = st.session_state.get("role", "?")
        st.error(
            f"**Permission denied by PostgreSQL.**\n\n"
            f"You are connected as `{role}`, and that role has not been granted "
            f"this privilege in `sql/05_roles.sql`.\n\n"
            f"The server's own message was:\n\n```\n{str(exc).strip()}\n```\n\n"
            f"Nothing in Python blocked this -- the request reached PostgreSQL "
            f"and PostgreSQL refused it."
        )
    else:
        st.error(f"```\n{str(exc).strip()}\n```")
