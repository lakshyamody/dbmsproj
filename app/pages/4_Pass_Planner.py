"""Pass Planner -- the rule-based fallback router, and the SAVEPOINT demo."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import theme  # noqa: E402

st.set_page_config(page_title="Pass Planner", page_icon="🗓️", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("planner")

st.title("🗓️ Pass Planner")
st.caption(
    "`plan_pass(cube_id, pass_id)` — the rule-based fallback router from "
    "KJS-SRS-01. Every packet gets a decision and a written reason."
)

DECISION_STYLE = {
    "TRANSMIT": "background-color:rgba(61,220,151,.14); color:#3ddc97",
    "DEFER":    "background-color:rgba(255,181,71,.14); color:#ffb547",
    "SKIP":     "background-color:rgba(255,255,255,.06); color:#8a8f98",
}


def style_decision(value):
    return DECISION_STYLE.get(value, "")


def pass_label(row) -> str:
    return (f"#{row.pass_id} · {row.start_time:%d %b %H:%M}"
            f"–{row.end_time:%H:%M} · link {row.max_link_score}")


# ---------------------------------------------------------------------------
# the rules
# ---------------------------------------------------------------------------
with st.expander("The rules the router applies", expanded=False):
    st.markdown(
        """
| # | Condition | Effect |
|---|---|---|
| Budget | `duration_seconds × (max_link_score × 12)` | bytes available this pass |
| R1 | latest battery **< 6.8 V** OR link score **< 40** | safe mode — **TT&C only** |
| R2 | latest battery **6.8 – 7.2 V** | TT&C + M17 + Codec2; **SSTV dropped** |
| R3 | otherwise | everything eligible |

Eligible packets are ordered by `payload_priority.priority`, then `ts`. A
`SUM(size_bytes) OVER (ORDER BY priority, ts)` window function gives the running
total; rows inside the budget are **TRANSMIT**, the rest **DEFER**. Payload
types excluded by R1/R2 come back as **SKIP** so nothing disappears silently.
        """
    )

# ---------------------------------------------------------------------------
# pick a cube and a pass
# ---------------------------------------------------------------------------
try:
    passes = db.query(
        """
        SELECT pass_id, cube_id, start_time, end_time, max_link_score
        FROM   ground_pass
        WHERE  start_time > now()
        ORDER  BY cube_id, start_time
        """
    )
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

if passes.empty:
    st.warning("No upcoming passes. Re-run `python scripts/setup_db.py` to refresh the schedule.")
    st.stop()

c1, c2 = st.columns([1, 2])
cube_id = c1.selectbox("Cube", sorted(passes["cube_id"].unique()))
cube_passes = passes[passes["cube_id"] == cube_id].reset_index(drop=True)
choice = c2.selectbox(
    "Upcoming pass",
    options=list(range(len(cube_passes))),
    format_func=lambda i: pass_label(cube_passes.iloc[i]),
)
pass_id = int(cube_passes.iloc[int(choice)]["pass_id"])

# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------
try:
    budget = db.query("SELECT * FROM pass_budget(%s)", (pass_id,)).iloc[0]
    plan = db.query(
        "SELECT * FROM plan_pass(%s, %s) ORDER BY queue_pos", (cube_id, pass_id)
    )
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

budget_bytes = int(budget["budget_bytes"])
transmit = plan[plan["decision"] == "TRANSMIT"]
used = int(transmit["size_bytes"].sum()) if not transmit.empty else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pass duration", f"{int(budget['duration_seconds'])} s")
m2.metric("Link score", int(budget["max_link_score"]),
          help=f"{int(budget['bytes_per_second'])} bytes/sec")
m3.metric("Byte budget", f"{budget_bytes:,}")
m4.metric("Queue depth", f"{len(plan):,} packets")

st.markdown("**Budget used**")
st.progress(min(1.0, used / budget_bytes) if budget_bytes else 0.0)
st.caption(
    f"{used:,} of {budget_bytes:,} bytes "
    f"({used / budget_bytes * 100:.1f}%) across "
    f"{len(transmit):,} packets marked TRANSMIT."
)

counts = plan["decision"].value_counts()
d1, d2, d3 = st.columns(3)
d1.metric("✅ TRANSMIT", int(counts.get("TRANSMIT", 0)))
d2.metric("⏸️ DEFER", int(counts.get("DEFER", 0)))
d3.metric("⏭️ SKIP", int(counts.get("SKIP", 0)))

# The headline reason, taken straight out of the function's own output.
skips = plan[plan["decision"] == "SKIP"]
if not skips.empty:
    st.warning(f"**Router decision:** {skips.iloc[0]['reason']}")
else:
    st.success("**Router decision:** all four payload types are eligible this pass.")

theme.section_label("Downlink queue")
show_all = st.checkbox("Show the whole queue", value=False)
view = plan if show_all else plan.head(60)
st.dataframe(
    view.style.map(style_decision, subset=["decision"]),
    width="stretch", hide_index=True,
)
if not show_all and len(plan) > 60:
    st.caption(f"Showing the first 60 of {len(plan):,} rows.")

st.markdown("**By payload type**")
summary = (
    plan.groupby(["payload_type", "decision"], as_index=False)
        .agg(packets=("packet_id", "count"), bytes=("size_bytes", "sum"))
        .sort_values(["payload_type", "decision"])
)
st.dataframe(
    summary.style.map(style_decision, subset=["decision"]),
    width="stretch", hide_index=True,
)

# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Execute the pass")
st.markdown(
    """
`execute_pass()` flips `sent = TRUE` on every TRANSMIT packet in two stages:

1. **TT&C first**, before the savepoint.
2. `SAVEPOINT` — in PL/pgSQL a `BEGIN … EXCEPTION` block *is* a savepoint.
3. **SSTV / M17 / Codec2** after it. If this stage fails, Postgres rolls back
   only to the savepoint and the TT&C from stage 1 still commits.
"""
)

e1, e2 = st.columns(2)
run_ok = e1.button("▶️ Execute Pass", type="primary", width="stretch")
run_fail = e2.button("💥 Execute with a stage-2 failure", width="stretch")

if run_ok or run_fail:
    simulate = bool(run_fail)
    try:
        before = db.query(
            "SELECT payload_type, count(*) AS unsent FROM telemetry "
            "WHERE cube_id = %s AND NOT sent GROUP BY payload_type ORDER BY payload_type",
            (cube_id,),
        )
        result = db.query(
            "SELECT * FROM execute_pass(%s, %s, %s)", (cube_id, pass_id, simulate)
        )
        after = db.query(
            "SELECT payload_type, count(*) AS unsent FROM telemetry "
            "WHERE cube_id = %s AND NOT sent GROUP BY payload_type ORDER BY payload_type",
            (cube_id,),
        )
    except Exception as exc:
        db.friendly_error(exc)
    else:
        st.dataframe(result, width="stretch", hide_index=True)

        rolled = (result["status"] == "ROLLED BACK TO SAVEPOINT").any()
        if rolled:
            st.warning(
                "Stage 2 raised, so Postgres rolled back **to the savepoint**. "
                "Stage 1's TT&C packets are still committed — look at the TT&C "
                "row in the before/after tables below."
            )
        else:
            st.success("Both stages committed.")

        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**Unsent before**")
            st.dataframe(before, width="stretch", hide_index=True)
        with b2:
            st.markdown("**Unsent after**")
            st.dataframe(after, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# the three-cube comparison
# ---------------------------------------------------------------------------
st.divider()
with st.expander("Compare CUBE01 vs CUBE02 vs CUBE03 side by side", expanded=True):
    st.caption(
        "Same function, same rules, three different spacecraft states — this is "
        "the comparison to show in the demo."
    )
    cols = st.columns(3)
    for col, cube in zip(cols, ["CUBE01", "CUBE02", "CUBE03"]):
        with col:
            st.markdown(f"### {cube}")
            sub = passes[passes["cube_id"] == cube]
            if sub.empty:
                st.info("No upcoming pass.")
                continue
            pid = int(sub.iloc[0]["pass_id"])
            try:
                cube_plan = db.query("SELECT * FROM plan_pass(%s, %s)", (cube, pid))
                cube_budget = db.query("SELECT * FROM pass_budget(%s)", (pid,)).iloc[0]
                latest_v = db.scalar(
                    "SELECT battery_voltage FROM telemetry WHERE cube_id = %s "
                    "ORDER BY ts DESC, packet_id DESC LIMIT 1",
                    (cube,),
                )
            except Exception as exc:
                db.friendly_error(exc)
                continue

            link = int(cube_budget["max_link_score"])
            st.markdown(
                f"Battery **{float(latest_v):.2f} V** · link **{link}**  \n"
                f"Budget **{int(cube_budget['budget_bytes']):,}** bytes"
            )

            per_decision = cube_plan["decision"].value_counts()
            st.markdown(
                f"✅ {int(per_decision.get('TRANSMIT', 0))} · "
                f"⏸️ {int(per_decision.get('DEFER', 0))} · "
                f"⏭️ {int(per_decision.get('SKIP', 0))}"
            )

            eligible = sorted(
                cube_plan[cube_plan["decision"] != "SKIP"]["payload_type"].unique()
            )
            st.markdown("**Eligible:** " + (", ".join(eligible) if eligible else "none"))

            cube_skips = cube_plan[cube_plan["decision"] == "SKIP"]
            if cube_skips.empty:
                st.success("All payload types eligible.")
            else:
                st.info(cube_skips.iloc[0]["reason"])

            st.dataframe(
                cube_plan.groupby(["payload_type", "decision"], as_index=False)
                         .agg(n=("packet_id", "count"))
                         .style.map(style_decision, subset=["decision"]),
                width="stretch", hide_index=True,
            )
