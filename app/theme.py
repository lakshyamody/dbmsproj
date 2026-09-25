"""
Presentation layer for SomaiyaSat Ground Control.

Nothing in here touches the database, the SQL or the permission model -- it is
purely the look of the dashboard. `inject_css()` runs once per page, right after
`st.set_page_config()`; `section_label()` renders the bracketed mono labels; and
importing this module registers the shared plotly template as the default so
every chart in the app comes out on the same black canvas.

Fonts are served from `app/static/fonts/` by Streamlit's own static file server
(`enableStaticServing = true` in .streamlit/config.toml), which puts them at
`/app/static/fonts/...`. There is no CDN anywhere in this project: the whole
dashboard renders with the network unplugged.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# palette -- the single source of truth, shared with the landing page
# ---------------------------------------------------------------------------
BLACK = "#000000"
NEAR_BLACK = "#0a0a0b"
WHITE = "#ffffff"
ACCENT = "#3d6bff"
ACCENT_SOFT = "#8ea6ff"
MUTED = "#8a8f98"
BORDER = "rgba(255,255,255,.12)"
SURFACE = "rgba(255,255,255,.05)"
RADIUS = "12px"

LINK_GOOD = "#3ddc97"
LINK_FAIR = "#ffb547"
LINK_POOR = "#ff5c7a"

FONT_SANS = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

STATIC_FONTS = "/app/static/fonts"

# Categorical series colours. Ordered so the first three are maximally
# separable, and none of them collide with the reserved link-quality hues used
# for status. A cube keeps its slot no matter which cubes are on screen.
COLORWAY = [ACCENT, "#3ddc97", "#ffb547", "#ff5c7a", ACCENT_SOFT, MUTED]

# Per-cube series colours, reused by the pages that plot one line per cube.
CUBE_COLOURS = {
    "CUBE01": ACCENT,
    "CUBE02": "#ffb547",
    "CUBE03": "#3ddc97",
    "CUBE04": ACCENT_SOFT,
}


def link_colour(score: int | float | None) -> str:
    """Link-quality colour: >=70 green, 40-69 amber, <40 red."""
    if score is None:
        return MUTED
    score = float(score)
    if score >= 70:
        return LINK_GOOD
    if score >= 40:
        return LINK_FAIR
    return LINK_POOR


# ---------------------------------------------------------------------------
# @font-face -- local woff2, no network
# ---------------------------------------------------------------------------
_FONT_FACES = "".join(
    f"""@font-face{{font-family:'Inter';font-style:normal;font-weight:{w};
    font-display:swap;src:url('{STATIC_FONTS}/inter-latin-{w}-normal.woff2')
    format('woff2');}}"""
    for w in (400, 500, 600, 700)
) + "".join(
    f"""@font-face{{font-family:'JetBrains Mono';font-style:normal;font-weight:{w};
    font-display:swap;src:url('{STATIC_FONTS}/jetbrains-mono-latin-{w}-normal.woff2')
    format('woff2');}}"""
    for w in (400, 500)
)


# ---------------------------------------------------------------------------
# the stylesheet
# ---------------------------------------------------------------------------
_CSS = f"""
{_FONT_FACES}

:root, .stApp {{
  --ss-black: {BLACK};
  --ss-near-black: {NEAR_BLACK};
  --ss-white: {WHITE};
  --ss-accent: {ACCENT};
  --ss-accent-soft: {ACCENT_SOFT};
  --ss-muted: {MUTED};
  --ss-border: {BORDER};
  --ss-surface: {SURFACE};
  --ss-radius: {RADIUS};
  --ss-good: {LINK_GOOD};
  --ss-fair: {LINK_FAIR};
  --ss-poor: {LINK_POOR};
  --ss-sans: {FONT_SANS};
  --ss-mono: {FONT_MONO};
}}

/* -- chrome we do not want ------------------------------------------------ */
header[data-testid="stHeader"],
div[data-testid="stDecoration"],
div[data-testid="stToolbar"],
div[data-testid="stStatusWidget"],
div[data-testid="stAppDeployButton"],
.stDeployButton,
#MainMenu,
footer {{
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}}

/* Keep the sidebar collapse control -- it is the only chrome that is useful. */
div[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapsedControl"] {{
  display: block !important;
  visibility: visible !important;
  height: auto !important;
}}

/* -- canvas --------------------------------------------------------------- */
html, body, .stApp, div[data-testid="stAppViewContainer"],
section[data-testid="stMain"] {{
  background: var(--ss-black) !important;
  color: var(--ss-white);
  font-family: var(--ss-sans);
  -webkit-font-smoothing: antialiased;
}}

div[data-testid="stMainBlockContainer"] {{
  padding-top: 2.6rem;
  padding-bottom: 5rem;
  max-width: 1380px;
}}

h1, h2, h3, h4, h5, h6 {{
  font-family: var(--ss-sans) !important;
  color: var(--ss-white) !important;
  letter-spacing: -0.02em;
  font-weight: 600 !important;
}}
h1 {{ font-size: 2.1rem !important; }}
h2 {{ font-size: 1.35rem !important; }}
h3 {{ font-size: 1.1rem !important; }}

p, li, span, label, div {{ font-family: var(--ss-sans); }}

div[data-testid="stCaptionContainer"],
div[data-testid="stCaptionContainer"] p,
small, .stCaption {{
  color: var(--ss-muted) !important;
  font-size: .8rem;
}}

a, a:visited {{ color: var(--ss-accent); text-decoration: none; }}
a:hover {{ color: var(--ss-accent-soft); text-decoration: underline; }}

hr, div[data-testid="stDivider"] hr {{
  border: none;
  border-top: 1px solid var(--ss-border);
  margin: 2rem 0;
}}

/* -- the bracketed section label ------------------------------------------ */
.ss-section-label {{
  font-family: var(--ss-mono);
  font-size: .68rem;
  font-weight: 500;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--ss-muted);
  margin: 1.9rem 0 .55rem;
  display: block;
}}

/* -- code / inline code --------------------------------------------------- */
code, kbd, pre, .stCode, div[data-testid="stCode"] * {{
  font-family: var(--ss-mono) !important;
}}
code {{
  background: rgba(61,107,255,.10) !important;
  color: var(--ss-accent-soft) !important;
  border: 1px solid rgba(61,107,255,.20);
  border-radius: 6px;
  padding: .08em .34em;
  font-size: .84em;
}}
div[data-testid="stCode"] {{
  border: 1px solid var(--ss-border);
  border-radius: var(--ss-radius);
  overflow: hidden;
  background: var(--ss-near-black);
}}
div[data-testid="stCode"] pre {{
  background: transparent !important;
  padding: .9rem 1rem !important;
}}
div[data-testid="stCode"] code {{
  background: transparent !important;
  border: none !important;
  color: #cfd3da !important;
  padding: 0 !important;
}}

/* -- buttons -------------------------------------------------------------- */
div[data-testid="stButton"] button,
div[data-testid="stFormSubmitButton"] button,
div[data-testid="stDownloadButton"] button {{
  font-family: var(--ss-sans) !important;
  font-size: .86rem !important;
  font-weight: 500 !important;
  border-radius: var(--ss-radius) !important;
  border: 1px solid var(--ss-border) !important;
  background: var(--ss-surface) !important;
  color: var(--ss-white) !important;
  box-shadow: none !important;
  padding: .52rem 1rem !important;
  transition: background .15s ease, border-color .15s ease, color .15s ease;
}}
div[data-testid="stButton"] button:hover,
div[data-testid="stFormSubmitButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {{
  background: rgba(61,107,255,.14) !important;
  border-color: rgba(61,107,255,.55) !important;
  color: var(--ss-white) !important;
}}
div[data-testid="stButton"] button:focus,
div[data-testid="stFormSubmitButton"] button:focus {{
  box-shadow: 0 0 0 2px rgba(61,107,255,.35) !important;
  outline: none !important;
}}
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stButton"] button[kind="primaryFormSubmit"],
div[data-testid="stFormSubmitButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {{
  background: var(--ss-accent) !important;
  border-color: var(--ss-accent) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
}}
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stButton"] button[kind="primaryFormSubmit"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:hover {{
  background: #5079ff !important;
  border-color: #5079ff !important;
}}

/* -- inputs --------------------------------------------------------------- */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stDateInput"] input {{
  background: var(--ss-near-black) !important;
  color: var(--ss-white) !important;
  font-family: var(--ss-sans) !important;
  caret-color: var(--ss-accent);
}}
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="textarea"],
div[data-testid="stNumberInputContainer"] {{
  background: var(--ss-near-black) !important;
  border: 1px solid var(--ss-border) !important;
  border-radius: var(--ss-radius) !important;
  box-shadow: none !important;
}}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="base-input"]:focus-within,
div[data-testid="stNumberInputContainer"]:focus-within {{
  border-color: rgba(61,107,255,.6) !important;
}}
div[data-testid="stNumberInputStepUp"],
div[data-testid="stNumberInputStepDown"] {{
  background: transparent !important;
  color: var(--ss-muted) !important;
  border-left: 1px solid var(--ss-border) !important;
}}
div[data-testid="stNumberInputStepUp"]:hover,
div[data-testid="stNumberInputStepDown"]:hover {{
  background: rgba(61,107,255,.14) !important;
  color: var(--ss-white) !important;
}}
input::placeholder, textarea::placeholder {{ color: #55595f !important; }}

div[data-testid="stWidgetLabel"] label,
div[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"] {{
  color: var(--ss-muted) !important;
  font-size: .78rem !important;
  font-weight: 500 !important;
  letter-spacing: .02em;
}}

/* -- select / multiselect ------------------------------------------------- */
div[data-baseweb="select"] > div {{
  background: var(--ss-near-black) !important;
  border: 1px solid var(--ss-border) !important;
  border-radius: var(--ss-radius) !important;
  color: var(--ss-white) !important;
  box-shadow: none !important;
}}
div[data-baseweb="select"] > div:hover {{ border-color: rgba(61,107,255,.45) !important; }}
div[data-baseweb="select"] svg {{ fill: var(--ss-muted); }}
div[data-baseweb="popover"] ul[role="listbox"],
div[data-baseweb="menu"] {{
  background: #0d0d0f !important;
  border: 1px solid var(--ss-border) !important;
  border-radius: var(--ss-radius) !important;
}}
div[data-baseweb="popover"] li[role="option"] {{
  background: transparent !important;
  color: #d4d7dc !important;
  font-family: var(--ss-sans) !important;
  font-size: .86rem !important;
}}
div[data-baseweb="popover"] li[role="option"]:hover,
div[data-baseweb="popover"] li[aria-selected="true"] {{
  background: rgba(61,107,255,.16) !important;
  color: var(--ss-white) !important;
}}
span[data-baseweb="tag"] {{
  background: rgba(61,107,255,.16) !important;
  border: 1px solid rgba(61,107,255,.35) !important;
  border-radius: 8px !important;
  color: #cfd8ff !important;
  font-family: var(--ss-mono) !important;
  font-size: .72rem !important;
}}
span[data-baseweb="tag"] span[role="presentation"] svg {{ fill: #cfd8ff !important; }}

/* -- checkbox / radio / toggle -------------------------------------------- */
div[data-testid="stCheckbox"] label span[data-baseweb="checkbox"] > div:first-child,
div[data-testid="stCheckbox"] span[data-baseweb="checkbox"] div[data-testid] {{
  border-color: var(--ss-border) !important;
}}
div[data-testid="stCheckbox"] label,
div[data-testid="stRadio"] label {{
  color: #d4d7dc !important;
  font-size: .86rem !important;
}}
div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {{
  border-color: var(--ss-border) !important;
}}

/* -- tabs ----------------------------------------------------------------- */
div[data-baseweb="tab-list"] {{
  background: transparent !important;
  border-bottom: 1px solid var(--ss-border);
  gap: .25rem;
}}
button[data-baseweb="tab"] {{
  background: transparent !important;
  color: var(--ss-muted) !important;
  font-family: var(--ss-mono) !important;
  font-size: .74rem !important;
  letter-spacing: .12em;
  text-transform: uppercase;
  padding: .55rem .9rem !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--ss-white) !important; }}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{
  background: var(--ss-accent) !important;
}}

/* -- metric --------------------------------------------------------------- */
div[data-testid="stMetric"] {{
  background: var(--ss-surface);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,.10);
  border-radius: var(--ss-radius);
  padding: .95rem 1.05rem;
}}
div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p {{
  color: var(--ss-muted) !important;
  font-family: var(--ss-mono) !important;
  font-size: .66rem !important;
  letter-spacing: .14em;
  text-transform: uppercase;
}}
div[data-testid="stMetricValue"] {{
  color: var(--ss-white) !important;
  font-family: var(--ss-mono) !important;
  font-weight: 500 !important;
  font-size: 1.55rem !important;
  letter-spacing: -.01em;
}}
div[data-testid="stMetricDelta"] {{
  font-family: var(--ss-mono) !important;
  font-size: .74rem !important;
}}
div[data-testid="stMetricDelta"] svg {{ display: none; }}

/* -- alerts: flat bordered tints, never a pastel block --------------------- */
div[data-testid="stAlert"] {{ background: transparent !important; }}
div[data-testid="stAlertContainer"],
div[data-testid="stNotification"] {{
  border-radius: var(--ss-radius) !important;
  border: 1px solid var(--ss-border) !important;
  background: var(--ss-surface) !important;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  color: #d4d7dc !important;
  box-shadow: none !important;
  padding: .85rem 1rem !important;
  font-size: .87rem;
}}
div[data-testid="stAlertContainer"] p {{ color: #d4d7dc !important; }}
div[data-testid="stAlertContainer"] strong {{ color: var(--ss-white) !important; }}
div[data-testid="stAlertContainer"] code {{ font-size: .8em; }}

div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]),
div[data-testid="stAlertContainer"].st-success {{
  border-color: rgba(61,220,151,.35) !important;
  background: rgba(61,220,151,.07) !important;
}}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
  border-color: rgba(255,92,122,.38) !important;
  background: rgba(255,92,122,.07) !important;
}}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
  border-color: rgba(255,181,71,.38) !important;
  background: rgba(255,181,71,.07) !important;
}}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
  border-color: rgba(61,107,255,.40) !important;
  background: rgba(61,107,255,.08) !important;
}}
div[data-testid="stAlertContainer"] svg {{ opacity: .9; }}

/* -- expander ------------------------------------------------------------- */
div[data-testid="stExpander"] {{
  border: 1px solid var(--ss-border) !important;
  border-radius: var(--ss-radius) !important;
  background: var(--ss-surface) !important;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  overflow: hidden;
}}
div[data-testid="stExpander"] details {{
  background: transparent !important;
  border: none !important;
}}
div[data-testid="stExpander"] summary {{
  background: transparent !important;
  color: #d4d7dc !important;
  font-family: var(--ss-mono) !important;
  font-size: .74rem !important;
  letter-spacing: .10em;
  text-transform: uppercase;
  padding: .75rem 1rem !important;
}}
div[data-testid="stExpander"] summary:hover {{ color: var(--ss-white) !important; }}
div[data-testid="stExpander"] summary svg {{ fill: var(--ss-muted); }}

/* -- dataframe / table ---------------------------------------------------- */
div[data-testid="stDataFrame"],
div[data-testid="stTable"],
div[data-testid="stJson"] {{
  border: 1px solid var(--ss-border);
  border-radius: var(--ss-radius);
  overflow: hidden;
  background: var(--ss-near-black);
}}
div[data-testid="stDataFrame"] * {{ font-family: var(--ss-sans); }}
div[data-testid="stJson"] {{ padding: .5rem .75rem; }}
div[data-testid="stJson"] * {{ font-family: var(--ss-mono) !important; font-size: .78rem !important; }}

/* markdown tables (st.markdown with a | table |) */
div[data-testid="stMarkdownContainer"] table {{
  border-collapse: collapse;
  border: 1px solid var(--ss-border);
  border-radius: var(--ss-radius);
  overflow: hidden;
  width: 100%;
  font-size: .85rem;
}}
div[data-testid="stMarkdownContainer"] th {{
  background: var(--ss-near-black);
  color: var(--ss-muted) !important;
  font-family: var(--ss-mono);
  font-size: .68rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  text-align: left;
  padding: .55rem .8rem;
  border-bottom: 1px solid var(--ss-border);
}}
div[data-testid="stMarkdownContainer"] td {{
  padding: .5rem .8rem;
  border-top: 1px solid rgba(255,255,255,.07);
  color: #d4d7dc;
}}

/* -- progress ------------------------------------------------------------- */
div[data-testid="stProgress"] > div > div {{
  background: rgba(255,255,255,.08) !important;
  border-radius: 999px !important;
  height: 8px !important;
}}
div[data-testid="stProgress"] > div > div > div {{
  background: var(--ss-accent) !important;
  border-radius: 999px !important;
}}

/* -- spinner / status ----------------------------------------------------- */
div[data-testid="stSpinner"] p,
div[data-testid="stSpinner"] i {{ color: var(--ss-muted) !important; }}

/* -- sidebar -------------------------------------------------------------- */
section[data-testid="stSidebar"] {{
  background: var(--ss-near-black) !important;
  border-right: 1px solid var(--ss-border);
}}
section[data-testid="stSidebar"] > div {{ background: transparent !important; }}
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] {{
  padding-top: .5rem;
}}
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a {{
  border-radius: 10px;
  color: var(--ss-muted) !important;
}}
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a span {{
  font-size: .85rem !important;
}}
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a:hover {{
  background: rgba(255,255,255,.05) !important;
  color: var(--ss-white) !important;
}}
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: rgba(61,107,255,.14) !important;
  color: var(--ss-white) !important;
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] li {{ font-size: .84rem; }}
section[data-testid="stSidebar"] div[data-testid="stAlertContainer"] {{
  font-size: .8rem;
  padding: .7rem .8rem !important;
}}

/* -- plotly --------------------------------------------------------------- */
div[data-testid="stPlotlyChart"] {{
  border: 1px solid var(--ss-border);
  border-radius: var(--ss-radius);
  background: var(--ss-surface);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  padding: .65rem;
}}
.js-plotly-plot .plotly .modebar {{ background: transparent !important; }}
.js-plotly-plot .plotly .modebar-btn path {{ fill: {MUTED} !important; }}
.js-plotly-plot .hoverlayer .hovertext {{ stroke: {BORDER} !important; }}

/* -- the embedded mission-control component ------------------------------- */
div[data-testid="stIFrame"], iframe {{
  border: none !important;
  background: transparent !important;
  color-scheme: dark;
}}

/* -- login card ----------------------------------------------------------- */
.ss-login-wrap,
.st-key-ss-login-card,
.st-key-ss-roles-card {{
  border: 1px solid rgba(255,255,255,.10);
  background: var(--ss-surface);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border-radius: 18px;
  padding: 1.5rem 1.6rem 1.2rem;
  margin-bottom: .6rem;
}}
.st-key-ss-login-card [data-testid="stForm"],
.st-key-ss-roles-card [data-testid="stForm"] {{
  border: none !important; padding: 0 !important; background: transparent !important;
}}
.ss-login-title {{
  font-size: 1.55rem; font-weight: 600; letter-spacing: -.02em;
  margin: 0 0 .35rem;
}}
.ss-login-sub {{ color: var(--ss-muted); font-size: .88rem; margin: 0 0 .2rem; }}
.ss-role-row {{
  display: flex; gap: .7rem; align-items: baseline;
  padding: .7rem 0; border-top: 1px solid rgba(255,255,255,.08);
}}
.ss-role-row:first-of-type {{ border-top: none; }}
.ss-role-name {{
  font-family: var(--ss-mono); font-size: .74rem; color: var(--ss-accent-soft);
  white-space: nowrap; letter-spacing: .02em;
}}
.ss-role-blurb {{ color: var(--ss-muted); font-size: .8rem; line-height: 1.45; }}
.ss-wordmark {{
  display: inline-flex; align-items: center; gap: 0;
  font-weight: 600; letter-spacing: -.015em; line-height: 1;
}}
.ss-wordmark .ss-glyph {{
  width: 1.02em; height: 1.02em; margin: 0 .01em; flex: none;
}}
.ss-pill {{
  display: inline-flex; align-items: center; gap: .4rem;
  font-family: var(--ss-mono); font-size: .66rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--ss-muted);
  border: 1px solid var(--ss-border); border-radius: 999px;
  padding: .26rem .62rem; background: var(--ss-surface);
}}
.ss-pill .ss-dot {{
  width: 6px; height: 6px; border-radius: 50%; background: var(--ss-good);
}}
"""

# One small original glyph: an orbit ring with a spacecraft dot on it. Used in
# place of the "a" in "Sat" for the wordmark.
ORBIT_GLYPH = (
    '<svg class="ss-glyph" viewBox="0 0 22 22" fill="none" aria-hidden="true">'
    '<ellipse cx="11" cy="11.5" rx="9.4" ry="4.5" transform="rotate(-28 11 11.5)" '
    f'stroke="{ACCENT}" stroke-width="1.7"/>'
    f'<circle cx="11" cy="11.5" r="3.6" fill="{ACCENT}" fill-opacity=".20" '
    f'stroke="{ACCENT}" stroke-width="1.5"/>'
    f'<circle cx="18.4" cy="7.3" r="1.85" fill="{ACCENT}"/>'
    '</svg>'
)


def inject_css() -> None:
    """Apply the mission-control stylesheet. Call once, after set_page_config."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def section_label(text: str) -> None:
    """Render a `[ SECTION ]` label in mono uppercase."""
    label = str(text).strip().upper()
    st.markdown(
        f'<span class="ss-section-label">[&nbsp;{label}&nbsp;]</span>',
        unsafe_allow_html=True,
    )


def wordmark(size: str = "1.05rem") -> str:
    """The SomaiyaSat wordmark, with the orbit glyph standing in for an 'a'."""
    return (
        f'<span class="ss-wordmark" style="font-size:{size}">'
        f'<span>SomaiyaS</span>{ORBIT_GLYPH}<span>t</span></span>'
    )


# ---------------------------------------------------------------------------
# shared plotly template
# ---------------------------------------------------------------------------
def _register_template():
    import plotly.graph_objects as go
    import plotly.io as pio

    axis = dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,.08)",
        gridwidth=1,
        zeroline=False,
        linecolor=BORDER,
        tickcolor=BORDER,
        tickfont=dict(family=FONT_MONO, size=11, color=MUTED),
        title=dict(font=dict(family=FONT_SANS, size=12, color=MUTED)),
        automargin=True,
    )

    template = go.layout.Template(
        layout=dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=COLORWAY,
            font=dict(family=FONT_SANS, size=12, color=WHITE),
            title=dict(font=dict(family=FONT_SANS, size=15, color=WHITE)),
            xaxis={**axis, "showgrid": False},
            yaxis=dict(axis),
            legend=dict(
                font=dict(family=FONT_MONO, size=11, color=MUTED),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
            ),
            hoverlabel=dict(
                bgcolor="#0d0d0f",
                bordercolor=BORDER,
                font=dict(family=FONT_MONO, size=11, color=WHITE),
            ),
            margin=dict(l=8, r=8, t=16, b=8),
            separators=".,",
        )
    )

    pio.templates["somaiyasat"] = template
    pio.templates.default = "somaiyasat"
    return template


PLOTLY_TEMPLATE = _register_template()
