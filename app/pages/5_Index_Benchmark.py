"""Index Benchmark -- EXPLAIN (ANALYZE, FORMAT JSON) with and without indexes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import theme  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_SQL = ROOT / "sql" / "06_indexes.sql"

st.set_page_config(page_title="Index Benchmark", page_icon="⚡", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("benchmark")

st.title("⚡ Index Benchmark")
st.caption(
    "The Telemetry Log's filter query, timed with and without the B-tree "
    "indexes in `sql/06_indexes.sql`."
)

BENCH_SQL = """
SELECT packet_id, cube_id, payload_type, battery_voltage, size_bytes, ts
FROM   telemetry
WHERE  cube_id = %s
  AND  ts BETWEEN now() - make_interval(hours => %s) AND now()
  AND  payload_type = %s
ORDER  BY ts DESC
"""

INDEX_NAMES = ["idx_telemetry_cube_ts", "idx_telemetry_payload_type"]

st.markdown(
    """
The query filters on **`cube_id`** (equality), **`ts`** (range) and
**`payload_type`** (equality). Without an index PostgreSQL has to read every
row in `telemetry` — a **Seq Scan**. With `(cube_id, ts)` it can jump straight
to the rows it needs.
"""
)

with st.expander("What gets created", expanded=False):
    try:
        st.code(INDEX_SQL.read_text(), language="sql")
    except OSError:
        st.warning("sql/06_indexes.sql not found.")

# ---------------------------------------------------------------------------
# current state
# ---------------------------------------------------------------------------
try:
    row_count = int(db.scalar("SELECT count(*) FROM telemetry"))
    existing = db.query(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename = 'telemetry' AND indexname = ANY(%s)",
        (INDEX_NAMES,),
    )
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

s1, s2, s3 = st.columns(3)
s1.metric("Rows in telemetry", f"{row_count:,}")
s2.metric("Benchmark indexes present", f"{len(existing)} / {len(INDEX_NAMES)}")

if row_count < 50_000:
    s3.warning("Small table — the planner may pick a Seq Scan either way.")

# ---------------------------------------------------------------------------
# optional bulk rows
# ---------------------------------------------------------------------------
with st.expander("Not seeing a difference? Add bulk rows", expanded=row_count < 50_000):
    st.markdown(
        "At ~5 000 rows the whole table fits in a couple of pages, so a Seq Scan "
        "is genuinely cheap and the planner may refuse the index. Generating "
        "200 000 extra packets makes the difference obvious."
    )
    if st.button("Generate 200 000 extra rows", width="stretch"):
        try:
            with st.spinner("Inserting 200 000 rows via generate_series…"):
                added = db.scalar("SELECT bench_bulk_load(%s)", (200_000,))
            st.success(f"Inserted {int(added):,} rows. Re-run the benchmark below.")
            st.rerun()
        except Exception as exc:
            db.friendly_error(exc)

# ---------------------------------------------------------------------------
# benchmark parameters
# ---------------------------------------------------------------------------
theme.section_label("Benchmark")
p1, p2, p3 = st.columns(3)
try:
    cube_options = db.query(
        "SELECT DISTINCT cube_id FROM telemetry ORDER BY cube_id"
    )["cube_id"].tolist()
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

bench_cube = p1.selectbox("cube_id", cube_options)
bench_type = p2.selectbox("payload_type", ["SSTV", "TT&C", "M17", "Codec2"])
WINDOWS = {"Last 6 hours": 6, "Last 24 hours": 24, "Last 3 days": 72, "Last 7 days": 168}
window_label = p3.selectbox("ts range", list(WINDOWS), index=0)
bench_hours = WINDOWS[window_label]

st.caption(
    "**Selectivity is the whole game.** A narrow `ts` range matches a small "
    "slice of the table and the index wins easily. Widen it to 7 days and the "
    "query touches most of the table, where a sequential scan is genuinely the "
    "cheaper plan — the planner is right to ignore the index. Try both."
)
st.code("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)" + BENCH_SQL, language="sql")


def explain() -> dict:
    """EXPLAIN (ANALYZE, FORMAT JSON) the benchmark query and return the plan."""
    raw = db.query(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + BENCH_SQL,
        (bench_cube, bench_hours, bench_type),
    )
    plan = raw.iat[0, 0]
    return json.loads(plan) if isinstance(plan, str) else plan


def node_types(node: dict, found: list[str] | None = None) -> list[str]:
    found = [] if found is None else found
    found.append(node.get("Node Type", "?"))
    for child in node.get("Plans", []) or []:
        node_types(child, found)
    return found


if st.button("▶️ Run benchmark (drop indexes → measure → create indexes → measure)",
             type="primary", width="stretch"):
    try:
        # --- 1. without indexes -------------------------------------------
        # bench_drop_indexes()/bench_create_indexes() are SECURITY DEFINER
        # wrappers around the DDL in sql/06_indexes.sql: ground_operator has
        # DML but does not own telemetry, so it cannot run CREATE INDEX itself.
        with st.spinner("Dropping indexes and measuring…"):
            db.scalar("SELECT bench_drop_indexes()")
            before_plan = explain()[0]["Plan"]

        # --- 2. with indexes ----------------------------------------------
        with st.spinner("Creating indexes and measuring…"):
            db.scalar("SELECT bench_create_indexes()")
            after_plan = explain()[0]["Plan"]

        st.session_state["bench"] = {
            "before": before_plan,
            "after": after_plan,
            "rows": row_count,
        }
    except Exception as exc:
        db.friendly_error(exc)

# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------
bench = st.session_state.get("bench")
if bench:
    before, after = bench["before"], bench["after"]
    t_before = float(before["Actual Total Time"])
    t_after = float(after["Actual Total Time"])
    n_before = node_types(before)
    n_after = node_types(after)

    scan_before = next((n for n in n_before if "Scan" in n), n_before[0])
    scan_after = next((n for n in n_after if "Scan" in n), n_after[0])

    theme.section_label("Result")
    r1, r2, r3 = st.columns(3)
    r1.metric("Without indexes", f"{t_before:.2f} ms")
    r1.caption(f"Plan: **{scan_before}**")
    r2.metric("With indexes", f"{t_after:.2f} ms")
    r2.caption(f"Plan: **{scan_after}**")
    if t_after > 0:
        speedup = t_before / t_after
        r3.metric("Speed-up", f"{speedup:.1f}×")
        r3.caption(f"**{t_before - t_after:.2f} ms** saved per run")

    if scan_before == scan_after:
        st.info(
            f"The planner chose **{scan_after}** both times, and it is right to. "
            f"With {bench['rows']:,} rows and this filter the query already "
            f"touches too much of the table for an index to pay off. Narrow the "
            f"`ts` range, or add the 200 000 bulk rows above, and run it again."
        )
    else:
        st.success(f"Plan changed: **{scan_before} → {scan_after}**.")

    # Two bars, one series -> one colour. Values direct-labelled.
    fig = go.Figure(
        go.Bar(
            x=["Without indexes", "With indexes"],
            y=[t_before, t_after],
            marker=dict(color=[theme.LINK_FAIR, theme.ACCENT], cornerradius=4),
            text=[f"{t_before:.2f} ms", f"{t_after:.2f} ms"],
            textposition="outside", textfont=dict(color=theme.WHITE),
            hovertemplate="<b>%{x}</b><br>%{y:.2f} ms<extra></extra>",
        )
    )
    fig.update_layout(
        template=theme.PLOTLY_TEMPLATE,
        height=320, margin=dict(l=8, r=8, t=28, b=8), bargap=0.55,
        showlegend=False,
        xaxis=dict(title=None),
        yaxis=dict(title="Execution time (ms)"),
    )
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Plan without indexes** — `{' → '.join(n_before)}`")
        st.metric("Rows returned", f"{int(before.get('Actual Rows', 0)):,}")
        st.json(before, expanded=False)
    with c2:
        st.markdown(f"**Plan with indexes** — `{' → '.join(n_after)}`")
        st.metric("Rows returned", f"{int(after.get('Actual Rows', 0)):,}")
        st.json(after, expanded=False)
else:
    st.info("Run the benchmark to see the before/after comparison.")
