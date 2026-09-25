"""Telemetry Log -- filtered DML browsing plus the DCL permission demo."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import theme  # noqa: E402

st.set_page_config(page_title="Telemetry Log", page_icon="📡", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("telemetry")

st.title("📡 Telemetry Log")
st.caption("Every packet buffered on board. `sent = false` means it is still queued for a pass.")

role = st.session_state["role"]

# ---------------------------------------------------------------------------
# Dropdown sources. ai_router cannot SELECT satellite_cube, but it *can* read
# comm_router -- which carries cube_id -- so the form still works for it.
# ---------------------------------------------------------------------------
try:
    cubes = db.query("SELECT cube_id FROM satellite_cube ORDER BY cube_id")["cube_id"].tolist()
except Exception:
    try:
        cubes = db.query(
            "SELECT cube_id FROM comm_router WHERE cube_id IS NOT NULL ORDER BY cube_id"
        )["cube_id"].tolist()
        st.info(
            "`satellite_cube` is not readable by your role, so the cube list was "
            "derived from `comm_router` instead."
        )
    except Exception as exc:
        db.friendly_error(exc)
        st.stop()

try:
    types = db.query(
        "SELECT payload_type FROM payload_priority ORDER BY priority"
    )["payload_type"].tolist()
except Exception:
    types = ["TT&C", "SSTV", "M17", "Codec2"]

# ---------------------------------------------------------------------------
# filters + paginated table
# ---------------------------------------------------------------------------
theme.section_label("Browse packets")

f1, f2, f3 = st.columns([1, 1, 1.4])
sel_cubes = f1.multiselect("Cube", cubes, default=cubes)
sel_types = f2.multiselect("Payload type", types, default=types)
date_range = f3.date_input(
    "Date range",
    value=(date.today() - timedelta(days=7), date.today()),
    max_value=date.today(),
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:  # the user is mid-selection
    start_date = end_date = date_range if isinstance(date_range, date) else date.today()

sent_filter = st.columns([1, 3])[0].selectbox(
    "Downlink state", ["All", "Unsent (queued)", "Sent"]
)

if not sel_cubes or not sel_types:
    st.info("Select at least one cube and one payload type.")
else:
    start_ts = datetime.combine(start_date, datetime.min.time())
    end_ts = datetime.combine(end_date, datetime.max.time())

    where = ["cube_id = ANY(%s)", "payload_type = ANY(%s)", "ts BETWEEN %s AND %s"]
    params: list = [sel_cubes, sel_types, start_ts, end_ts]
    if sent_filter == "Unsent (queued)":
        where.append("sent = FALSE")
    elif sent_filter == "Sent":
        where.append("sent = TRUE")
    where_sql = " AND ".join(where)

    try:
        total = int(db.scalar(
            f"SELECT count(*) FROM telemetry WHERE {where_sql}", tuple(params)
        ))

        PAGE_SIZE = 50
        pages = max(1, -(-total // PAGE_SIZE))

        m1, m2, m3 = st.columns(3)
        m1.metric("Matching packets", f"{total:,}")
        m2.metric("Pages", f"{pages:,}")
        page = m3.number_input("Page", min_value=1, max_value=pages, value=1, step=1)
        offset = (int(page) - 1) * PAGE_SIZE

        rows = db.query(
            f"""
            SELECT packet_id, cube_id, payload_type, battery_voltage, temperature,
                   size_bytes, ts, sent
            FROM   telemetry
            WHERE  {where_sql}
            ORDER  BY ts DESC, packet_id DESC
            LIMIT  %s OFFSET %s
            """,
            tuple(params) + (PAGE_SIZE, offset),
        )
        st.dataframe(rows, width="stretch", hide_index=True)

        with st.expander("The SQL behind this table"):
            st.code(
                "SELECT packet_id, cube_id, payload_type, battery_voltage, temperature,\n"
                "       size_bytes, ts, sent\n"
                "FROM   telemetry\n"
                f"WHERE  {where_sql}\n"
                "ORDER  BY ts DESC, packet_id DESC\n"
                f"LIMIT  {PAGE_SIZE} OFFSET {offset};",
                language="sql",
            )
            st.caption(
                "This is the exact shape of the query the Index Benchmark page "
                "tunes: equality on `cube_id`, a range on `ts`, equality on "
                "`payload_type`."
            )
    except Exception as exc:
        st.markdown("**Reading `telemetry` was refused:**")
        db.friendly_error(exc)

# ---------------------------------------------------------------------------
# the DCL demo
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Insert a test packet")

st.markdown(
    f"""
You are connected as **`{role}`**. This form always sends the INSERT to
PostgreSQL — nothing here is disabled in Python. What happens next is decided
purely by the grants in `sql/05_roles.sql`:

| role | result |
|---|---|
| `ground_operator` | allowed — INSERT on every table |
| `ai_router` | allowed — INSERT on `telemetry` specifically |
| `student_analyst` | **refused** — read-only, so the server raises *permission denied* |
"""
)

with st.form("insert_packet"):
    c1, c2, c3 = st.columns(3)
    in_cube = c1.selectbox("Cube", cubes)
    in_type = c2.selectbox("Payload type", types)
    in_size = c3.number_input("Size (bytes)", min_value=1, max_value=100_000, value=128)
    c4, c5 = st.columns(2)
    in_volts = c4.number_input("Battery (V)", min_value=0.0, max_value=9.99, value=7.80, step=0.01)
    in_temp = c5.number_input("Temperature (°C)", min_value=-40.0, max_value=99.9, value=25.0, step=0.5)
    send_it = st.form_submit_button("Insert packet", type="primary")

if send_it:
    try:
        # No RETURNING clause on purpose: RETURNING needs SELECT privilege on
        # the columns it hands back, which ai_router does not have.
        db.execute(
            """
            INSERT INTO telemetry
                (cube_id, payload_type, battery_voltage, temperature, size_bytes, ts, sent)
            VALUES (%s, %s, %s, %s, %s, now(), FALSE)
            """,
            (in_cube, in_type, in_volts, in_temp, int(in_size)),
        )
        st.success(
            f"Packet inserted for {in_cube}. Role `{role}` holds INSERT on `telemetry`."
        )
    except Exception as exc:
        db.friendly_error(exc)
