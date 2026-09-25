"""Health Dashboard -- aggregates, GROUP BY / HAVING, and a CASE health flag."""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import theme  # noqa: E402

st.set_page_config(page_title="Health Dashboard", page_icon="🔋", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("health")

st.title("🔋 Health Dashboard")
st.caption("`v_cube_health` and `v_low_battery_cubes` — GROUP BY, HAVING and CASE.")

# Categorical slots 1-3, fixed per cube. Colour follows the entity, so a cube
# keeps its hue no matter which other cubes are on screen.
CUBE_COLOURS = theme.CUBE_COLOURS

# Reserved status palette - never reused for a series.
STATUS = {
    "HEALTHY":       (theme.LINK_GOOD, "✅"),
    "WARNING":       (theme.LINK_FAIR, "⚠️"),
    "THERMAL WATCH": (theme.LINK_FAIR, "🌡️"),
    "CRITICAL":      (theme.LINK_POOR, "⛔"),
    "NO DATA":       (theme.MUTED, "—"),
}

INK = theme.WHITE
INK_MUTED = theme.MUTED
GRID = "rgba(255,255,255,.08)"

# ---------------------------------------------------------------------------
# low battery banner (HAVING)
# ---------------------------------------------------------------------------
try:
    low = db.query("SELECT * FROM v_low_battery_cubes")
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

if low.empty:
    st.success("No cube is averaging below 7.0 V over the last 24 hours.")
else:
    names = ", ".join(low["cube_id"].tolist())
    st.error(
        f"⛔ **Low battery — {names}.** "
        f"Averaging under 7.0 V over the last 24 hours, so the pass planner will "
        f"start dropping payload types for these cubes."
    )
    st.dataframe(
        low.style.set_properties(
            **{"background-color": "rgba(255,92,122,.14)", "color": "#ff5c7a"}
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "`v_low_battery_cubes` — `GROUP BY cube_id HAVING AVG(battery_voltage) < 7.0`, "
        "restricted to the last 24 hours."
    )

# ---------------------------------------------------------------------------
# per-cube health (GROUP BY + CASE)
# ---------------------------------------------------------------------------
theme.section_label("Per-cube health")
health = db.query("SELECT * FROM v_cube_health")

cols = st.columns(len(health))
for col, (_, row) in zip(cols, health.iterrows()):
    colour, icon = STATUS.get(row["health_flag"], (theme.MUTED, "—"))
    latest = row["latest_battery"]
    col.markdown(
        f"**{row['cube_id']}**  \n"
        f"<span style='color:{colour};font-weight:600'>{icon} {row['health_flag']}</span>",
        unsafe_allow_html=True,
    )
    col.metric(
        "Latest battery",
        f"{latest:.2f} V" if latest is not None else "—",
        delta=(f"{float(latest) - 7.0:+.2f} V vs 7.0 V threshold"
               if latest is not None else None),
        delta_color="normal",
    )
    col.caption(
        f"{int(row['packet_count']):,} packets · {int(row['unsent_count']):,} queued"
    )

# The table view: the relief for series colours that sit under 3:1 contrast,
# and the raw numbers a marker will want to see.
st.dataframe(health, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# battery voltage over time
# ---------------------------------------------------------------------------
theme.section_label("Battery voltage over time")
st.caption(
    "Hourly average per cube — `GROUP BY cube_id, date_trunc('hour', ts)`. "
    "The dashed line is the 7.0 V threshold from `v_low_battery_cubes`."
)

volts = db.query(
    """
    SELECT cube_id,
           date_trunc('hour', ts)     AS hour,
           ROUND(AVG(battery_voltage), 3) AS avg_v
    FROM   telemetry
    GROUP  BY cube_id, date_trunc('hour', ts)
    ORDER  BY cube_id, hour
    """
)

if volts.empty:
    st.info("No telemetry yet. Run `python scripts/generate_telemetry.py`.")
else:
    fig = go.Figure()
    for cube_id, grp in volts.groupby("cube_id"):
        grp = grp.sort_values("hour")
        colour = CUBE_COLOURS.get(cube_id, theme.ACCENT_SOFT)
        fig.add_trace(
            go.Scatter(
                x=grp["hour"], y=grp["avg_v"].astype(float),
                name=cube_id, mode="lines",
                line=dict(color=colour, width=2),
                hovertemplate=f"<b>{cube_id}</b><br>%{{x|%d %b %H:%M}}<br>%{{y:.2f}} V<extra></extra>",
            )
        )
        # Direct label at the end of each line: identity is never colour-alone.
        last = grp.iloc[-1]
        fig.add_annotation(
            x=last["hour"], y=float(last["avg_v"]), text=f" {cube_id}",
            showarrow=False, xanchor="left", font=dict(color=colour, size=12),
        )

    fig.add_hline(
        y=7.0, line=dict(color=INK_MUTED, width=1.5, dash="dash"),
        annotation_text="7.0 V threshold", annotation_position="bottom left",
        annotation_font=dict(color=INK_MUTED, size=11),
    )
    fig.update_layout(
        template=theme.PLOTLY_TEMPLATE,
        height=420,
        margin=dict(l=8, r=90, t=8, b=8),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(title=None),
        yaxis=dict(title="Volts"),
    )
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# packets per payload type
# ---------------------------------------------------------------------------
theme.section_label("Packets per payload type")
st.caption("`v_payload_mix` — the UNION view, filtered to its per-payload-type half.")

mix = db.query(
    "SELECT bucket, priority, packet_count, total_bytes FROM v_payload_mix "
    "WHERE bucket_kind = 'BY PAYLOAD TYPE' ORDER BY priority"
)

if not mix.empty:
    left, right = st.columns([2, 1])

    with left:
        bar = go.Figure(
            go.Bar(
                x=mix["bucket"], y=mix["packet_count"].astype(int),
                marker=dict(color=theme.ACCENT, cornerradius=4),
                text=[f"{int(v):,}" for v in mix["packet_count"]],
                textposition="outside", textfont=dict(color=INK),
                hovertemplate="<b>%{x}</b><br>%{y:,} packets<extra></extra>",
            )
        )
        bar.update_layout(
            template=theme.PLOTLY_TEMPLATE,
            height=340, margin=dict(l=8, r=8, t=24, b=8), bargap=0.45,
            showlegend=False,
            xaxis=dict(title=None),
            yaxis=dict(title="Packets"),
        )
        st.plotly_chart(bar, width="stretch")

    with right:
        show = mix.copy()
        show["total_MB"] = (show["total_bytes"].astype(float) / 1_048_576).round(1)
        st.dataframe(
            show[["bucket", "priority", "packet_count", "total_MB"]],
            width="stretch", hide_index=True,
        )
        st.caption(
            "TT&C dominates by packet count but is tiny by volume — which is "
            "exactly why it is cheap to always transmit first."
        )
