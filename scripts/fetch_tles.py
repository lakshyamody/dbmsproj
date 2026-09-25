#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- TLE fetcher.

Downloads current two-line element sets from CelesTrak for the tracked fleet
and UPSERTs them into satellite_tle.

    python scripts/fetch_tles.py             # download, then load
    python scripts/fetch_tles.py --offline   # load from the cached file only
    python scripts/fetch_tles.py --list      # show what is in the DB, no writes

Two things worth knowing about this script.

FIRST -- it is the one place in the project that talks to the public internet.
Everything else runs entirely from localhost, and the dashboard still does: the
download happens here, ahead of time, and the result is cached under
data/tle_cache/ and stored in the database. So the app keeps working offline,
and --offline reproduces a load without any network at all.

SECOND -- it is the project's UPSERT. CelesTrak republishes elements for the
same satellite several times a day, and norad_id is that satellite's permanent
catalogue number, so a re-fetch must UPDATE the existing row rather than insert
a duplicate:

    INSERT INTO satellite_tle (...) VALUES (...)
    ON CONFLICT (norad_id) DO UPDATE SET ...
    WHERE EXCLUDED.epoch_utc > satellite_tle.epoch_utc

The WHERE on the DO UPDATE matters: it refuses to overwrite a newer element set
with an older one, which can genuinely happen when two CelesTrak groups are
merged in one run. Without it the load order would silently decide your orbits.

Connects as ground_operator, because refreshing orbital data is an operator
action -- student_analyst is granted SELECT on satellite_tle but no INSERT, so
running this as the analyst is refused by PostgreSQL.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _conn   # noqa: E402
import _orbit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "tle_cache"
GROUND_OPERATOR_PASSWORD = os.getenv("GROUND_OPERATOR_PASSWORD", "ground123")

TIMEOUT_S = 30
USER_AGENT = "SomaiyaSat-Ground-Control/1.0 (student project; contact via GitHub)"


# ---------------------------------------------------------------------------
# download / cache
# ---------------------------------------------------------------------------
def cache_path(group: str) -> Path:
    return CACHE_DIR / f"{group}.tle"


def download_group(group: str) -> str | None:
    """Fetch one CelesTrak group, or None if the network is unavailable."""
    url = _orbit.CELESTRAK_URL.format(group=group)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"    {group}: download failed ({exc})")
        return None

    # CelesTrak answers with a 200 and a plain-text apology when it rate-limits,
    # so a successful HTTP status is not enough -- check it parses as TLEs.
    if "1 " not in body or len(body.strip().splitlines()) < 3:
        print(f"    {group}: response was not TLE data (rate limited?)")
        return None
    return body


def load_group(group: str, offline: bool) -> list[tuple[str, str, str]]:
    """TLE records for one group, from the network if allowed, else the cache."""
    path = cache_path(group)
    body: str | None = None

    if not offline:
        body = download_group(group)
        if body is not None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            print(f"    {group}: downloaded, cached to {path.relative_to(ROOT)}")

    if body is None:
        if not path.exists():
            print(f"    {group}: no cache at {path.relative_to(ROOT)}, skipping")
            return []
        body = path.read_text(encoding="utf-8")
        age_h = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 3600
        print(f"    {group}: using cache ({age_h:.1f} h old)")

    return _orbit.parse_tle_text(body)


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------
def connect_operator():
    """ground_operator if possible, else the owner (so setup still works)."""
    try:
        return _conn.connect(user="ground_operator",
                             password=GROUND_OPERATOR_PASSWORD), "ground_operator"
    except psycopg2.OperationalError:
        cfg = _conn.settings()
        print("  could not connect as ground_operator; using the owner instead")
        return _conn.connect(), cfg["user"]


def upsert(rows: list[tuple]) -> tuple[int, int]:
    """
    Load the element sets. Returns (rows_sent, rows_actually_written).

    The difference between the two numbers is the point: a re-run sends the
    same satellites but writes nothing, because every epoch is already current.
    """
    conn, who = connect_operator()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM satellite_tle")
            before = cur.fetchone()[0]

            execute_values(
                cur,
                """
                INSERT INTO satellite_tle
                    (norad_id, object_name, tle_line1, tle_line2, epoch_utc,
                     inclination_deg, mean_motion, period_min, eccentricity,
                     payload_modes, source, fetched_at)
                VALUES %s
                ON CONFLICT (norad_id) DO UPDATE SET
                    object_name     = EXCLUDED.object_name,
                    tle_line1       = EXCLUDED.tle_line1,
                    tle_line2       = EXCLUDED.tle_line2,
                    epoch_utc       = EXCLUDED.epoch_utc,
                    inclination_deg = EXCLUDED.inclination_deg,
                    mean_motion     = EXCLUDED.mean_motion,
                    period_min      = EXCLUDED.period_min,
                    eccentricity    = EXCLUDED.eccentricity,
                    payload_modes   = EXCLUDED.payload_modes,
                    source          = EXCLUDED.source,
                    fetched_at      = EXCLUDED.fetched_at
                -- never let an older element set overwrite a newer one
                WHERE EXCLUDED.epoch_utc > satellite_tle.epoch_utc
                """,
                rows,
                page_size=100,
            )
            written = cur.rowcount
            cur.execute("SELECT count(*) FROM satellite_tle")
            after = cur.fetchone()[0]
        conn.commit()
    except psycopg2.errors.InsufficientPrivilege as exc:
        conn.rollback()
        print(f"\n  PERMISSION DENIED as {who} -- PostgreSQL refused the INSERT:\n    {exc}")
        raise SystemExit(1)
    finally:
        conn.close()

    print(f"  loaded as {who}: {len(rows)} sent, {written} written "
          f"({after - before} new, {written - (after - before)} updated)")
    return len(rows), written


def show() -> None:
    conn = _conn.connect()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT norad_id, object_name, payload_modes,
                   inclination_deg, period_min, tle_age_days, tle_status,
                   upcoming_passes
            FROM   v_tracked_fleet
            """
        )
        rows = cur.fetchall()
    conn.close()

    if not rows:
        print("  satellite_tle is empty -- run without --list first")
        return
    print(f"\n  {'NORAD':>6}  {'object':22} {'modes':14} {'incl':>7} "
          f"{'period':>7} {'TLE age':>8} {'status':7} {'passes':>6}")
    for nid, name, modes, incl, per, age, status, up in rows:
        print(f"  {nid:>6}  {name[:22]:22} {(modes or '-')[:14]:14} "
              f"{incl:>7} {per:>7} {age:>7}d {status:7} {up:>6}")


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip the download and load from data/tle_cache/")
    ap.add_argument("--all", action="store_true",
                    help="load every satellite in the groups, not just the fleet")
    ap.add_argument("--list", action="store_true",
                    help="print what is already in the database and exit")
    args = ap.parse_args()

    print("SomaiyaSat Ground Control -- TLE fetch")
    print(f"  target {_conn.describe()}")

    if args.list:
        show()
        return

    print(f"\n  source: CelesTrak groups {', '.join(_orbit.CELESTRAK_GROUPS)}"
          f"{' (offline, cache only)' if args.offline else ''}")

    # Merge the groups; a satellite appearing in both is kept once, newest first.
    found: dict[int, tuple] = {}
    for group in _orbit.CELESTRAK_GROUPS:
        for name, l1, l2 in load_group(group, args.offline):
            if not args.all and name not in _orbit.TRACKED_FLEET:
                continue
            try:
                nid = _orbit.norad_id(l1)
                epoch = _orbit.tle_epoch(l1)
                el = _orbit.tle_elements(l2)
            except (ValueError, IndexError):
                continue          # malformed record; skip rather than abort
            row = (
                nid, name[:60], l1.ljust(69)[:69], l2.ljust(69)[:69], epoch,
                round(el["inclination_deg"], 3), round(el["mean_motion"], 8),
                round(el["period_min"], 3), round(el["eccentricity"], 7),
                _orbit.TRACKED_FLEET.get(name, "TT&C"),
                f"celestrak:{group}", datetime.now(timezone.utc),
            )
            prev = found.get(nid)
            if prev is None or epoch > prev[4]:
                found[nid] = row

    if not found:
        print("\n  nothing to load. Either the download failed and there is no "
              "cache, or none of the tracked fleet appeared in the groups.")
        raise SystemExit(1)

    missing = sorted(set(_orbit.TRACKED_FLEET) - {r[1] for r in found.values()})
    if missing and not args.all:
        print(f"\n  not found in the published groups: {', '.join(missing)}")
        print("  (satellites are removed from CelesTrak's lists when they re-enter)")

    print()
    upsert(sorted(found.values(), key=lambda r: r[0]))
    show()
    print("\nDone. Next: python scripts/predict_passes.py")


if __name__ == "__main__":
    main()
