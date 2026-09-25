"""SomaiyaSat Ground Control -- login + mission-control screen + mission status."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import db
import theme

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
GLOBE_TEMPLATE = APP_DIR / "components" / "globe_template.html"
STATS_FILE = APP_DIR / "data" / "stats.json"

st.set_page_config(
    page_title="SomaiyaSat Ground Control",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed" if not db.is_logged_in() else "auto",
)
theme.inject_css()


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------
if not db.is_logged_in():
    st.markdown(
        "<div style='height:6vh'></div>", unsafe_allow_html=True
    )
    pad_l, centre, pad_r = st.columns([1, 1.5, 1])

    with centre:
        st.markdown(
            f"<div style='display:flex;justify-content:center;margin-bottom:1.1rem'>"
            f"{theme.wordmark('1.25rem')}</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="ss-login-card"):
            st.markdown(
                "<p class='ss-login-title'>Sign in</p>"
                "<p class='ss-login-sub'>Pick a database role and enter its "
                "password. The dashboard connects to PostgreSQL <b>as that "
                "role</b> — every permission you have from here on is enforced "
                "by the server, not by this app.</p>",
                unsafe_allow_html=True,
            )
            with st.form("login", border=False):
                role = st.selectbox(
                    "Database role",
                    options=list(db.ROLES),
                    format_func=lambda r: f"{db.ROLES[r]['label']}  ({r})",
                )
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Connect", width="stretch", type="primary"
                )

        if submitted:
            ok, err = db.login(role, password)
            if ok:
                st.rerun()
            else:
                st.error(f"Login failed.\n\n```\n{err}\n```")

        theme.section_label("the three roles")
        rows = "".join(
            f"<div class='ss-role-row'><span class='ss-role-name'>{name}</span>"
            f"<span class='ss-role-blurb'>{meta['blurb']}</span></div>"
            for name, meta in db.ROLES.items()
        )
        with st.container(key="ss-roles-card"):
            st.markdown(rows, unsafe_allow_html=True)
        st.caption(
            "Passwords are the ones in your `.env` "
            "(`GROUND_OPERATOR_PASSWORD`, `STUDENT_ANALYST_PASSWORD`, "
            "`AI_ROUTER_PASSWORD`)."
        )

    st.stop()

# ---------------------------------------------------------------------------
# logged in -- the mission-control screen
# ---------------------------------------------------------------------------
db.sidebar("home")

role = st.session_state["role"]


@st.cache_data(show_spinner=False)
def load_stats(mtime: float) -> dict:
    """app/data/stats.json, exported by scripts/export_stats.py."""
    try:
        return json.loads(STATS_FILE.read_text())
    except (OSError, ValueError):
        return {"satellites": [], "payloads": [], "passes": [], "stations": [],
                "tracked": [], "tracked_passes": [], "totals": {},
                "source": "unavailable"}


@st.cache_data(show_spinner=False, ttl=120)
def live_stats(role_key: str) -> dict | None:
    """
    Build the globe payload straight from the database, as the logged-in role.

    Why this exists: stats.json is a file, and a deployed instance serves
    whatever was committed. Orbital data expires -- element sets age and pass
    windows pass -- so a baked file stops being true within a day and the
    countdowns would all read PASS WINDOW OPEN. Reading live keeps the deployed
    dashboard honest.

    Returns None if it cannot be built, and the caller falls back to the file.
    Cached for two minutes so panning the globe does not re-query.
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import export_stats
        return export_stats.from_database(conn=db.get_conn())
    except Exception:
        # Any failure at all -- a role without SELECT (ai_router has none), a
        # dropped connection, a schema mismatch -- falls back to the file.
        return None


def mission_control(payload: dict) -> None:
    """One self-contained component: globe + panels, all assets served locally."""
    html = GLOBE_TEMPLATE.read_text()
    blob = json.dumps(payload).replace("</", "<\\/").replace(" ", "\\u2028")
    components.html(html.replace("/*__DATA__*/", blob), height=860, scrolling=False)


# Live from the database where the role can read it; the exported file otherwise.
stats = live_stats(role)
if stats is None:
    stats = load_stats(STATS_FILE.stat().st_mtime if STATS_FILE.exists() else 0.0)
else:
    stats = dict(stats, source="live")
stats_for_view = dict(stats)
stats_for_view["role"] = role

mission_control(stats_for_view)

totals = stats.get("totals", {})
if totals:
    m = st.columns(5)
    m[0].metric("Satellites", totals.get("satellites", "—"))
    m[1].metric("Deployed", totals.get("deployed_satellites", "—"))
    m[2].metric("Ground stations", totals.get("ground_stations", "—"))
    m[3].metric("Packets buffered", f"{totals.get('packets', 0):,}")
    m[4].metric("Queued for downlink", f"{totals.get('unsent_packets', 0):,}")
    n_tracked = totals.get("tracked_objects", 0)
    st.caption(
        f"**CUBE01–03 are the proposed mission** — not in orbit, so their tracks "
        f"are an analytic sun-synchronous model. "
        + (f"The **{n_tracked} hollow markers are real satellites**, propagated "
           f"from live CelesTrak element sets with SGP4 — see Live Tracking. "
           if n_tracked else
           "No real element sets loaded; run `python scripts/fetch_tles.py`. ")
        + (f"Figures are read **live from PostgreSQL** as `{role}`."
           if stats.get("source") == "live" else
           f"Figures come from `app/data/stats.json` "
           f"(source: `{stats.get('source', '?')}`) — regenerate with "
           f"`python scripts/export_stats.py`.")
    )

# ---------------------------------------------------------------------------
# the brief
# ---------------------------------------------------------------------------
theme.section_label("the mission")
st.markdown(
    """
SomaiyaSat is a PocketQube deployed by the SomaiyaPod deployer, carrying
multi-mode amateur radio payloads for the global HAM community. It is only in
view of the ground station for a few minutes at a time, and an onboard AI
scheduler/router has to decide, live, what to spend that window on. The mission
sets the order: TT&C / housekeeping always highest, then SSTV imagery, then
Codec2 / M17 voice and data.

Use case KJS-SRS-01 rates **AI Security & Trustworthiness as High** — the router
must "implement watchdogs/fallback rule-based logic in case AI model output is
anomalous" — and **Responsible AI as Medium**, requiring the decision logic be
"explainable to the ground team (e.g. logged rationale for prioritization
choices)".

This project is that fallback, built on the ground-station side in SQL: the
rules live in PL/pgSQL, every decision carries a written reason, and the whole
thing is reproducible from the database alone.
"""
)

st.info(f"Connected to `{db.PGDATABASE}` as **{role}** — {db.ROLES[role]['label']}")

# ---------------------------------------------------------------------------
# mission status
# ---------------------------------------------------------------------------
theme.section_label("mission status")
st.caption(
    "`v_mission_status` — a three-way JOIN across `deployer_pod`, "
    "`satellite_cube` and `comm_router`, with a CASE-derived chain status."
)

try:
    status = db.query("SELECT * FROM v_mission_status")
except Exception as exc:  # ai_router has no SELECT on the views
    db.friendly_error(exc)
else:
    def colour_chain(value: str) -> str:
        return {
            "OPERATIONAL":         "background-color:rgba(61,220,151,.14); color:#3ddc97",
            "AWAITING DEPLOYMENT": "background-color:rgba(255,181,71,.14); color:#ffb547",
            "DEPLOY FAILED":       "background-color:rgba(255,92,122,.16); color:#ff5c7a",
            "DEGRADED":            "background-color:rgba(255,181,71,.16); color:#ffb547",
        }.get(value, "")

    st.dataframe(
        status.style.map(colour_chain, subset=["chain_status"]),
        width="stretch",
        hide_index=True,
    )

    operational = int((status["chain_status"] == "OPERATIONAL").sum())
    a, b, c = st.columns(3)
    a.metric("Pods", len(status))
    b.metric("Operational chains", operational)
    c.metric("Awaiting deployment", int((status["chain_status"] == "AWAITING DEPLOYMENT").sum()))

st.divider()
st.markdown(
    "Use the pages in the sidebar: **Deployment Tracker**, **Telemetry Log**, "
    "**Health Dashboard**, **Pass Planner** and **Index Benchmark**."
)
