"""Deployment Tracker -- the COMMIT / ROLLBACK demo."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import theme  # noqa: E402

st.set_page_config(page_title="Deployment Tracker", page_icon="🚀", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("deployment")

st.title("🚀 Deployment Tracker")
st.caption(
    "`CALL confirm_deployment(pod_id, simulate_failure)` — one procedure, "
    "one transaction, three statements that must all land or all vanish."
)


def pods_and_cubes():
    return db.query(
        """
        SELECT p.pod_id, p.mech_type, p.confirm_status, p.launch_date,
               c.cube_id, c.sys_init, c.power_state
        FROM   deployer_pod p
        LEFT JOIN satellite_cube c ON c.pod_id = p.pod_id
        ORDER BY p.pod_id
        """
    )


# ---------------------------------------------------------------------------
# current state
# ---------------------------------------------------------------------------
theme.section_label("Pods and cubes")
try:
    state = pods_and_cubes()
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

def colour_status(value):
    return {
        "Confirmed": "background-color:rgba(61,220,151,.14); color:#3ddc97",
        "Pending":   "background-color:rgba(255,181,71,.14); color:#ffb547",
        "Failed":    "background-color:rgba(255,92,122,.16); color:#ff5c7a",
        "Complete":  "background-color:rgba(61,220,151,.14); color:#3ddc97",
        "Standby":   "background-color:rgba(255,181,71,.14); color:#ffb547",
    }.get(value, "")

st.dataframe(
    state.style.map(colour_status, subset=["confirm_status", "sys_init"]),
    width="stretch",
    hide_index=True,
)

# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
theme.section_label("Run a deployment")

pod_ids = state["pod_id"].tolist()
default_index = pod_ids.index("POD04") if "POD04" in pod_ids else 0
pod_id = st.selectbox("Pod", pod_ids, index=default_index)

st.markdown(
    """
The procedure does three things in order:

1. `UPDATE deployer_pod` → `Confirmed`, `launch_date = CURRENT_DATE`
2. `UPDATE satellite_cube` → `sys_init = 'Complete'`, `power_state = 'Nominal'`
3. `INSERT INTO deployment_log` → the audit row

**Simulate Failed Deployment** raises an exception *between steps 1 and 2*.
Step 1 has already run at that point, so the rollback is what un-does it.
"""
)

col_ok, col_fail, col_reset = st.columns(3)
confirm_clicked = col_ok.button("✅ Confirm Deployment", width="stretch", type="primary")
fail_clicked = col_fail.button("💥 Simulate Failed Deployment", width="stretch")
reset_clicked = col_reset.button("↺ Reset POD04 for the demo", width="stretch")


def snapshot(pod: str):
    """The two rows the transaction touches, so we can diff before/after."""
    return db.query(
        """
        SELECT p.pod_id, p.confirm_status, p.launch_date, c.cube_id, c.sys_init, c.power_state
        FROM   deployer_pod p
        LEFT JOIN satellite_cube c ON c.pod_id = p.pod_id
        WHERE  p.pod_id = %s
        """,
        (pod,),
    )


if confirm_clicked or fail_clicked:
    simulate = bool(fail_clicked)

    try:
        before = snapshot(pod_id)
    except Exception as exc:
        db.friendly_error(exc)
        st.stop()

    ok, message = db.confirm_deployment(pod_id, simulate_failure=simulate)
    after = snapshot(pod_id)

    st.divider()
    if ok:
        st.success(f"**COMMIT** — {message}")
    elif message.startswith("PERMISSION DENIED"):
        st.error(
            f"**Permission denied by PostgreSQL.** Your role has no EXECUTE on "
            f"this procedure.\n\n```\n{message}\n```"
        )
    else:
        st.warning("**ROLLBACK** — the transaction was aborted and undone.")
        st.code(message, language="text")

    left, right = st.columns(2)
    with left:
        st.markdown("**State before**")
        st.dataframe(before, width="stretch", hide_index=True)
    with right:
        st.markdown("**State after**")
        st.dataframe(after, width="stretch", hide_index=True)

    if before.equals(after):
        st.info(
            "The two tables are **identical** — the rolled-back transaction left "
            "no trace in `deployer_pod` or `satellite_cube`."
        )
        st.caption(
            "The failed attempt was still recorded in `deployment_log`, written "
            "in a *separate* transaction after the ROLLBACK. An INSERT inside "
            "the procedure would have been rolled back with everything else."
        )
    else:
        st.info("The two tables differ — the transaction committed.")

if reset_clicked:
    try:
        db.execute("CALL reset_deployment_demo()")
        st.success("POD04 / CUBE04 are back to Pending / Standby. Run the demo again.")
        st.rerun()
    except Exception as exc:
        db.friendly_error(exc)

# ---------------------------------------------------------------------------
# audit trail
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Deployment log")
st.caption("Every attempt, including the ones that were rolled back.")
try:
    log = db.query(
        "SELECT log_id, pod_id, cube_id, action, outcome, logged_at "
        "FROM deployment_log ORDER BY log_id DESC"
    )
    def colour_outcome(value):
        return {
            "SUCCESS":     "background-color:rgba(61,220,151,.14); color:#3ddc97",
            "ROLLED_BACK": "background-color:rgba(255,92,122,.16); color:#ff5c7a",
        }.get(value, "")

    st.dataframe(
        log.style.map(colour_outcome, subset=["outcome"]),
        width="stretch",
        hide_index=True,
    )
except Exception as exc:
    db.friendly_error(exc)
