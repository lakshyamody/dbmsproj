"""
Live Tracking -- real satellites, real orbits, real pass windows.

Everything on this page is real data. The element sets come from CelesTrak,
the pass windows are computed by SGP4, and the link scores are computed in SQL
by link_score_from_pass() from the actual pass geometry.

Why this page exists: SomaiyaSat has not launched, so it has no orbit to track.
A real mission validates its ground segment against satellites already flying
before committing to its own launch -- and these ten amateur-radio satellites
are the flight heritage behind the modes KJS-SRS-01 proposes.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "scripts"))
import db  # noqa: E402
import theme  # noqa: E402

st.set_page_config(page_title="Live Tracking", page_icon="📡", layout="wide")
theme.inject_css()
db.require_login()
db.sidebar("tracking")

st.title("📡 Live Tracking")
st.caption(
    "Real satellites from CelesTrak, propagated with SGP4. `satellite_tle` is "
    "loaded by an **UPSERT**; `tracked_pass` holds windows computed from actual "
    "orbital geometry, with the link score derived in SQL."
)

TLE_STATUS_STYLE = {
    "FRESH":  f"background-color:rgba(61,220,151,.14); color:{theme.LINK_GOOD}",
    "AGEING": f"background-color:rgba(255,181,71,.14); color:{theme.LINK_FAIR}",
    "STALE":  f"background-color:rgba(255,92,122,.14); color:{theme.LINK_POOR}",
}
GRADE_STYLE = {
    "FULL - all modes":       f"background-color:rgba(61,220,151,.14); color:{theme.LINK_GOOD}",
    "REDUCED - SSTV at risk": f"background-color:rgba(255,181,71,.14); color:{theme.LINK_FAIR}",
    "SAFE MODE - TT&C only":  f"background-color:rgba(255,92,122,.14); color:{theme.LINK_POOR}",
}


def fmt_countdown(seconds: float | int | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    s = int(seconds)
    if s <= 0:
        return "PASS OPEN"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sec:02d}s"


# ---------------------------------------------------------------------------
# is there any data yet?
# ---------------------------------------------------------------------------
try:
    n_tle = db.scalar("SELECT count(*) FROM satellite_tle") or 0
    n_pass = db.scalar("SELECT count(*) FROM tracked_pass WHERE los_utc > now()") or 0
except Exception as exc:  # role without SELECT, or tables missing
    db.friendly_error(exc)
    st.stop()

if n_tle == 0:
    st.warning(
        "No element sets loaded yet. Run:\n\n"
        "```\npython scripts/fetch_tles.py\npython scripts/predict_passes.py\n```"
    )
    st.stop()

with st.expander("Where this data comes from, and what is real", expanded=False):
    st.markdown(
        """
| Layer | Real? | Source |
|---|---|---|
| Orbital element sets (`satellite_tle`) | **Real** | CelesTrak, fetched by `scripts/fetch_tles.py` |
| Satellite positions | **Real** | SGP4 propagation of those elements |
| Pass windows (`tracked_pass`) | **Real** | computed geometry over `ground_station` coordinates |
| Link scores | **Derived** | `link_score_from_pass(elevation, range)` in SQL |
| SomaiyaSat CUBE01–03 | **Proposed** | not in orbit; see the Pass Planner |

**The link model.** Two effects dominate a LEO amateur link, and both follow
from pass geometry:

- free-space path loss rises as the square of slant range → `20·log₁₀(range / 500 km)` dB
- near the horizon the signal crosses far more atmosphere → `10·log₁₀(1 / sin(elevation))` dB

Summed and mapped onto 0–100 across a 30 dB span. That calibration puts a
marginal 10° pass just above the 40-point safe-mode threshold `plan_pass()`
uses — so a rule invented for the proposed mission turns out to fire on exactly
the passes a real operator would distrust.

**No M17 heritage.** None of these satellites flies M17. It is a recent open
digital-voice standard, and that absence is visible in the `payload_modes`
column rather than merely asserted — it is the gap the use case aims at.
        """
    )

# ---------------------------------------------------------------------------
# the tracked fleet
# ---------------------------------------------------------------------------
theme.section_label("Tracked fleet")
st.markdown("##### Element sets and their freshness")
st.caption(
    "A TLE is a snapshot of an orbit that drifts away from reality over days, "
    "so its **age** is the most important thing about it. `v_tracked_fleet` "
    "grades it and counts each object's upcoming passes with a correlated subquery."
)

try:
    fleet = db.query(
        """
        SELECT object_name, norad_id, payload_modes, inclination_deg,
               period_min, tle_age_days, tle_status, upcoming_passes
        FROM   v_tracked_fleet
        """
    )
except Exception as exc:
    db.friendly_error(exc)
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Satellites tracked", int(len(fleet)))
c2.metric("Upcoming passes", int(n_pass))
c3.metric("Freshest TLE", f"{fleet['tle_age_days'].min():.2f} d")
stale = int((fleet["tle_status"] != "FRESH").sum())
c4.metric("Ageing or stale", stale, delta=None if stale == 0 else "re-run fetch_tles.py",
          delta_color="off")

show = fleet.rename(columns={
    "object_name": "Object", "norad_id": "NORAD", "payload_modes": "Modes flown",
    "inclination_deg": "Incl °", "period_min": "Period min",
    "tle_age_days": "TLE age (d)", "tle_status": "TLE", "upcoming_passes": "Passes",
})
st.dataframe(
    show.style.map(lambda v: TLE_STATUS_STYLE.get(v, ""), subset=["TLE"]),
    width="stretch", hide_index=True,
)

# ---------------------------------------------------------------------------
# next passes
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Next passes")

stations = db.query(
    """
    SELECT station_id, name, country, latitude, longitude, altitude_m,
           min_elevation_deg, is_primary
    FROM   ground_station
    -- KJSSE first: it is the mission's own station. is_primary alone would put
    -- Helsinki ahead of it, since both are primary and 'HEL' < 'KJSSE'.
    ORDER  BY (station_id = 'KJSSE') DESC, is_primary DESC, station_id
    """
)
labels = {
    r.station_id: f"{r.name} ({r.country}) · mask {r.min_elevation_deg:g}°"
    for r in stations.itertuples()
}
ids = list(labels)
default_ix = ids.index("KJSSE") if "KJSSE" in ids else 0
station_id = st.selectbox(
    "Ground station", list(labels), index=default_ix,
    format_func=lambda k: labels[k],
)
srow = stations[stations.station_id == station_id].iloc[0]

st.markdown(
    f"##### Upcoming windows over {srow['name']}  "
    f"<span style='color:{theme.MUTED};font-weight:400'>"
    f"{float(srow['latitude']):.3f}°, {float(srow['longitude']):.3f}°</span>",
    unsafe_allow_html=True,
)
st.caption(
    "`v_next_passes` — a three-way JOIN (`tracked_pass` → `satellite_tle` → "
    "`ground_station`), graded by the same thresholds the router uses."
)

upcoming = db.query(
    """
    SELECT track_id, object_name, payload_modes, aos_utc, los_utc,
           duration_s, seconds_until_aos, max_elevation_deg,
           range_km_at_max, max_link_score, link_grade
    FROM   v_next_passes
    WHERE  station_id = %s
    ORDER  BY aos_utc
    LIMIT  20
    """,
    (station_id,),
)

if upcoming.empty:
    st.info(
        f"No upcoming passes over {srow['name']} in the forecast horizon. "
        "Extend it with `python scripts/predict_passes.py --hours 48`."
    )
else:
    tbl = pd.DataFrame({
        "Object": upcoming.object_name,
        "AOS (UTC)": pd.to_datetime(upcoming.aos_utc, utc=True).dt.strftime("%d %b %H:%M:%S"),
        "In": upcoming.seconds_until_aos.map(fmt_countdown),
        "Duration": (upcoming.duration_s / 60).map(lambda m: f"{m:.1f} min"),
        "Max elev": upcoming.max_elevation_deg.map(lambda d: f"{float(d):.1f}°"),
        "Range": upcoming.range_km_at_max.map(lambda r: f"{float(r):,.0f} km"),
        "Link": upcoming.max_link_score,
        "Grade": upcoming.link_grade,
    })
    st.dataframe(
        tbl.style.map(lambda v: GRADE_STYLE.get(v, ""), subset=["Grade"]),
        width="stretch", hide_index=True,
    )

    # ----------------------------------------------------------------- profile
    st.markdown("##### Elevation profile")
    st.caption(
        "The selected pass, propagated with SGP4 at 10-second resolution. This "
        "curve is the pass — the shaded band is the station's horizon mask, and "
        "the peak is what sets the link score."
    )

    def pass_label(row) -> str:
        return (f"{row.object_name} · {pd.Timestamp(row.aos_utc).tz_convert('UTC'):%d %b %H:%M}"
                f" UTC · {float(row.max_elevation_deg):.0f}° · link {row.max_link_score}")

    choice = st.selectbox(
        "Pass", list(range(len(upcoming))),
        format_func=lambda i: pass_label(upcoming.iloc[i]),
    )
    sel = upcoming.iloc[choice]

    try:
        import _orbit  # from scripts/, shared with the predictor
        from sgp4.api import Satrec

        tle = db.query(
            """
            SELECT t.tle_line1, t.tle_line2, t.object_name
            FROM   satellite_tle t
            JOIN   tracked_pass p ON p.norad_id = t.norad_id
            WHERE  p.track_id = %s
            """,
            (int(sel.track_id),),
        )
        sat = Satrec.twoline2rv(tle.iloc[0].tle_line1.strip(),
                               tle.iloc[0].tle_line2.strip())

        aos = pd.Timestamp(sel.aos_utc).to_pydatetime()
        los = pd.Timestamp(sel.los_utc).to_pydatetime()
        pad = timedelta(seconds=90)
        ts, els = [], []
        t = aos - pad
        while t <= los + pad:
            sp = _orbit.subpoint(sat, t)
            if sp is not None:
                el, _rng = _orbit.look_angles(
                    float(srow["latitude"]), float(srow["longitude"]),
                    float(srow["altitude_m"]) / 1000.0,
                    *sp,
                )
                ts.append(t)
                els.append(el)
            t += timedelta(seconds=10)

        mask = float(srow["min_elevation_deg"])
        fig = go.Figure()
        fig.add_hrect(y0=-5, y1=mask, fillcolor=theme.MUTED, opacity=0.14,
                      line_width=0, annotation_text=f"below {mask:g}° mask",
                      annotation_position="bottom right",
                      annotation_font_color=theme.MUTED)
        fig.add_trace(go.Scatter(
            x=ts, y=els, mode="lines", name="Elevation",
            line=dict(color=theme.ACCENT, width=2.5),
            hovertemplate="%{x|%H:%M:%S} UTC<br>%{y:.1f}°<extra></extra>",
        ))
        peak_ix = int(pd.Series(els).idxmax())
        fig.add_trace(go.Scatter(
            x=[ts[peak_ix]], y=[els[peak_ix]], mode="markers+text",
            marker=dict(color=theme.LINK_GOOD, size=11,
                        line=dict(color="#000", width=2)),
            text=[f" {els[peak_ix]:.1f}°"], textposition="middle right",
            textfont=dict(color=theme.LINK_GOOD),
            name="Peak", hoverinfo="skip",
        ))
        fig.update_layout(
            template=theme.PLOTLY_TEMPLATE, height=330, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="UTC", yaxis_title="Elevation (degrees)",
            # Scale to the pass rather than pinning 0-90: most amateur passes
            # peak well under 30 degrees, and a fixed axis flattens them into
            # an unreadable line along the bottom. The floor keeps the horizon
            # mask visible so low passes still read as low.
            yaxis=dict(range=[-5, max(float(els[peak_ix]) * 1.35, 30.0)]),
        )
        st.plotly_chart(fig, width="stretch")

        st.caption(
            f"Peak {els[peak_ix]:.1f}° at {ts[peak_ix]:%H:%M:%S} UTC · "
            f"stored max {float(sel.max_elevation_deg):.1f}° · "
            f"link score {sel.max_link_score} → {sel.link_grade}"
        )
    except Exception as exc:
        st.info(f"Elevation profile unavailable: {exc}")

# ---------------------------------------------------------------------------
# station workload
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Ground segment")
st.markdown("##### 24-hour workload per station")
st.caption(
    "`v_station_workload` — a LEFT JOIN with GROUP BY aggregates, so a station "
    "with no contacts still appears with zeros rather than vanishing."
)

workload = db.query(
    """
    SELECT station_id, name, country, is_primary, min_elevation_deg,
           passes_24h, distinct_objects, avg_max_elevation,
           best_elevation, avg_link_score, contact_minutes
    FROM   v_station_workload
    """
)

left, right = st.columns([3, 2])
with left:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=workload.contact_minutes.astype(float),
        y=workload.name,
        orientation="h",
        marker=dict(
            color=[theme.ACCENT if p else theme.ACCENT_SOFT
                   for p in workload.is_primary],
            line=dict(width=0),
        ),
        hovertemplate="%{y}<br>%{x:.0f} contact minutes<extra></extra>",
    ))
    fig.update_layout(
        template=theme.PLOTLY_TEMPLATE, height=300, showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Contact minutes in 24 h", yaxis_title=None,
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, width="stretch")

with right:
    st.dataframe(
        workload[["station_id", "passes_24h", "distinct_objects",
                  "avg_max_elevation", "contact_minutes"]].rename(columns={
            "station_id": "Stn", "passes_24h": "Passes",
            "distinct_objects": "Objects", "avg_max_elevation": "Avg el°",
            "contact_minutes": "Contact min",
        }),
        width="stretch", hide_index=True,
    )

top = workload.iloc[0]
st.info(
    f"**{top['name']} leads with {float(top['contact_minutes']):.0f} contact minutes.** "
    "This is real orbital mechanics, not a weighting: most of these satellites "
    "are in near-polar orbits, whose ground tracks converge at high latitude. "
    "A high-latitude station therefore sees far more of each orbit than an "
    "equatorial one — which is exactly why polar ground stations exist."
)

# ---------------------------------------------------------------------------
# the model, interactive
# ---------------------------------------------------------------------------
st.divider()
theme.section_label("Link model")
st.markdown("##### `link_score_from_pass(elevation, range)` — computed by PostgreSQL")
st.caption(
    "The score below is calculated by the database, not by Python. Move the "
    "sliders to see where the 40-point safe-mode threshold falls."
)

m1, m2, m3 = st.columns([2, 2, 3])
with m1:
    el_in = st.slider("Max elevation (°)", 1.0, 90.0, 25.0, 0.5)
with m2:
    rng_in = st.slider("Range at peak (km)", 300, 2500, 900, 10)
with m3:
    try:
        score = db.scalar("SELECT link_score_from_pass(%s, %s)", (el_in, rng_in))
        grade = ("SAFE MODE — TT&C only" if score < 40
                 else "REDUCED — SSTV at risk" if score < 70
                 else "FULL — all modes")
        colour = theme.link_colour(score)
        st.markdown(
            f"<div style='padding:.6rem 0'>"
            f"<div style='font:600 2.6rem/1 {theme.FONT_MONO};color:{colour}'>{score}</div>"
            f"<div style='color:{colour};font-size:.9rem;margin-top:.3rem'>{grade}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    except Exception as exc:
        db.friendly_error(exc)

st.caption(
    "This is the bridge between the two halves of the project: real pass "
    "geometry on this page produces the same 0–100 score that "
    "`comm_router.link_score` carries for the proposed mission, so "
    "`plan_pass()` reasons about both in exactly the same terms."
)
