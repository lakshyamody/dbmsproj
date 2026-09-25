#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- run everything.

    python run.py

  1. Builds the landing page if landing/dist is missing or out of date.
  2. Exports stats.json from PostgreSQL (or mock data if the DB is down).
  3. Serves landing/dist on http://localhost:5500
  4. Starts Streamlit on http://localhost:8501
  5. Opens the landing page in your browser.

Ctrl+C stops both servers.

Flags:
  --no-build     never rebuild the landing page
  --rebuild      always rebuild, even if dist looks fresh
  --no-open      do not open a browser
  --mock         force mock stats, ignore the database
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANDING = ROOT / "landing"
DIST = LANDING / "dist"
SCRIPTS = ROOT / "scripts"

LANDING_PORT = 5500
STREAMLIT_PORT = 8501

# Prefer the project venv so it works without activating anything.
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def dist_is_stale() -> bool:
    index = DIST / "index.html"
    if not index.exists():
        return True
    built = index.stat().st_mtime

    # Any source newer than the bundle means a rebuild is due.
    watched = [LANDING / "index.html", LANDING / "package.json", LANDING / "vite.config.ts"]
    src = LANDING / "src"
    if src.exists():
        watched += [p for p in src.rglob("*") if p.is_file()]
    return any(p.stat().st_mtime > built for p in watched if p.exists())


def build_landing() -> bool:
    if not (LANDING / "node_modules").exists():
        log("landing/node_modules is missing — running npm install (one time)")
        r = subprocess.run(["npm", "install"], cwd=LANDING)
        if r.returncode != 0:
            log("npm install FAILED — the landing page will not be served")
            return False

    log("building the landing page (npm run build)…")
    r = subprocess.run(["npm", "run", "build"], cwd=LANDING)
    if r.returncode != 0:
        log("npm run build FAILED")
        return False
    log(f"built -> {DIST.relative_to(ROOT)}")
    return True


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
def export_stats(mock: bool) -> None:
    cmd = [PY, str(SCRIPTS / "export_stats.py")]
    if mock:
        cmd.append("--mock")
    subprocess.run(cmd, cwd=ROOT)


# ---------------------------------------------------------------------------
# static server
# ---------------------------------------------------------------------------
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ without logging every asset request."""

    def log_message(self, *_args):  # noqa: D102
        pass

    def end_headers(self):
        # Never cache during a demo — a stale bundle is the classic confusion.
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


class ReusableServer(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve_landing() -> ReusableServer | None:
    if not (DIST / "index.html").exists():
        log("landing/dist is empty — skipping the static server")
        return None

    handler = functools.partial(QuietHandler, directory=str(DIST))
    try:
        httpd = ReusableServer(("127.0.0.1", LANDING_PORT), handler)
    except OSError as exc:
        log(f"could not bind :{LANDING_PORT} — {exc}")
        return None

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    log(f"landing page  ->  http://localhost:{LANDING_PORT}")
    return httpd


# ---------------------------------------------------------------------------
# streamlit
# ---------------------------------------------------------------------------
def start_streamlit() -> subprocess.Popen | None:
    if port_busy(STREAMLIT_PORT):
        log(f"something is already listening on :{STREAMLIT_PORT} — leaving it alone")
        return None

    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [
            PY, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py"),
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    for _ in range(60):
        if port_busy(STREAMLIT_PORT):
            log(f"dashboard     ->  http://localhost:{STREAMLIT_PORT}")
            return proc
        if proc.poll() is not None:
            log("streamlit exited immediately — run it by hand to see why:")
            log(f"  {PY} -m streamlit run app/Home.py")
            return None
        time.sleep(0.5)

    log("streamlit did not come up in 30s; continuing anyway")
    return proc


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    print("\nSomaiyaSat Ground Control\n" + "-" * 46)

    # 1. build
    if args.rebuild or (not args.no_build and dist_is_stale()):
        if not build_landing():
            log("continuing without a fresh landing build")
    else:
        log("landing/dist is up to date")

    # 2. stats (after the build, so dist/data survives)
    export_stats(args.mock)

    # 3 + 4. servers
    httpd = serve_landing()
    streamlit = start_streamlit()

    if httpd is None and streamlit is None:
        log("nothing to serve — exiting")
        raise SystemExit(1)

    # 5. browser
    url = (
        f"http://localhost:{LANDING_PORT}"
        if httpd
        else f"http://localhost:{STREAMLIT_PORT}"
    )
    if not args.no_open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print("-" * 46)
    print("  Ctrl+C to stop\n")

    stop = threading.Event()

    def shutdown(_sig=None, _frm=None):
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop.is_set():
            # If Streamlit dies on its own, don't keep pretending it is up.
            if streamlit is not None and streamlit.poll() is not None:
                log("streamlit stopped")
                streamlit = None
            stop.wait(0.5)
    finally:
        print("\n  shutting down…")
        if streamlit is not None and streamlit.poll() is None:
            streamlit.terminate()
            try:
                streamlit.wait(timeout=6)
            except subprocess.TimeoutExpired:
                streamlit.kill()
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        log("done")


if __name__ == "__main__":
    main()
