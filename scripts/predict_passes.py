#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- real pass prediction.

Propagates every element set in satellite_tle with SGP4 and writes the
resulting visibility windows into tracked_pass.

    python scripts/predict_passes.py                  # next 24 h, all stations
    python scripts/predict_passes.py --hours 48
    python scripts/predict_passes.py --station KJSSE  # one station only
    python scripts/predict_passes.py --show           # print, write nothing

No network access: the elements are already in the database, so this runs
entirely offline. Only fetch_tles.py touches the internet.

Two design notes.

WHERE THE LINK SCORE COMES FROM. The script computes pass GEOMETRY -- when the
satellite rises, when it sets, how high it gets, how far away it is at its best.
It does not compute the link score in Python. The INSERT calls
link_score_from_pass() so the radio model lives in SQL alongside the rule that
consumes it, and changing the model means changing one function, not re-running
this script.

WHY IT DELETES BEFORE INSERTING. tracked_pass has UNIQUE (norad_id, station_id,
aos_utc), which makes an identical recomputation idempotent. But a re-run after
a TLE refresh legitimately produces a slightly DIFFERENT acquisition time for
the same physical pass -- a few seconds' difference is a better forecast, not a
second pass. So a run first clears the horizon it is about to recompute, and the
ON CONFLICT clause then only has to absorb the boundary case. Past passes are
never touched: they are the record of what was actually predicted at the time.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from sgp4.api import Satrec

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _conn   # noqa: E402
import _orbit  # noqa: E402

GROUND_OPERATOR_PASSWORD = os.getenv("GROUND_OPERATOR_PASSWORD", "ground123")


def connect_operator():
    try:
        return _conn.connect(user="ground_operator",
                             password=GROUND_OPERATOR_PASSWORD), "ground_operator"
    except psycopg2.OperationalError:
        print("  could not connect as ground_operator; using the owner instead")
        return _conn.connect(), _conn.settings()["user"]


def read_inputs(conn, station_filter: str | None):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT norad_id, object_name, tle_line1, tle_line2, payload_modes
            FROM   satellite_tle
            ORDER  BY object_name
            """
        )
        sats = cur.fetchall()

        if station_filter:
            cur.execute(
                """
                SELECT station_id, name, latitude, longitude, altitude_m,
                       min_elevation_deg
                FROM   ground_station WHERE station_id = %s
                """,
                (station_filter,),
            )
        else:
            cur.execute(
                """
                SELECT station_id, name, latitude, longitude, altitude_m,
                       min_elevation_deg
                FROM   ground_station ORDER BY is_primary DESC, station_id
                """
            )
        stations = cur.fetchall()
    return sats, stations


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0,
                    help="forecast horizon in hours (default 24)")
    ap.add_argument("--station", help="limit to one station_id")
    ap.add_argument("--show", action="store_true",
                    help="print the forecast without writing to the database")
    ap.add_argument("--step", type=int, default=30,
                    help="coarse search step in seconds (default 30)")
    args = ap.parse_args()

    print("SomaiyaSat Ground Control -- pass prediction")
    print(f"  target {_conn.describe()}")

    conn, who = connect_operator()
    try:
        sats, stations = read_inputs(conn, args.station)
    finally:
        if args.show:
            pass

    if not sats:
        print("\n  satellite_tle is empty. Run: python scripts/fetch_tles.py")
        conn.close()
        raise SystemExit(1)
    if not stations:
        print(f"\n  no such station: {args.station!r}")
        conn.close()
        raise SystemExit(1)

    start = datetime.now(timezone.utc).replace(microsecond=0)
    print(f"\n  propagating {len(sats)} satellites over {len(stations)} stations")
    print(f"  window {start:%Y-%m-%d %H:%M} UTC + {args.hours:g} h, "
          f"{args.step}s coarse step\n")

    rows: list[tuple] = []
    skipped: list[str] = []

    for nid, name, l1, l2, _modes in sats:
        try:
            sat = Satrec.twoline2rv(l1.strip(), l2.strip())
        except Exception as exc:                       # unusable element set
            skipped.append(f"{name}: {exc}")
            continue

        total = 0
        for sid, sname, lat, lon, alt_m, min_el in stations:
            found = _orbit.find_passes(
                sat,
                float(lat), float(lon), float(alt_m) / 1000.0,
                start, args.hours, float(min_el),
                coarse_s=args.step,
            )
            for p in found:
                rows.append((nid, sid, p["aos_utc"], p["los_utc"],
                             p["max_elevation_deg"], p["range_km_at_max"]))
            total += len(found)
        print(f"    {name[:24]:24} {total:3d} passes")

    if skipped:
        print("\n  skipped (unusable elements):")
        for s in skipped:
            print(f"    {s}")

    if not rows:
        print("\n  no passes found in the window. That is possible for a short "
              "horizon, but check the station coordinates if it persists.")
        conn.close()
        return

    if args.show:
        print(f"\n  {len(rows)} passes (not written; --show)\n")
        print(f"  {'sat':>6} {'stn':6} {'AOS (UTC)':16} {'dur':>6} {'max el':>7} {'range':>8}")
        for nid, sid, aos, los, el, rng in sorted(rows, key=lambda r: r[2])[:25]:
            print(f"  {nid:>6} {sid:6} {aos:%m-%d %H:%M:%S}  "
                  f"{(los-aos).total_seconds()/60:5.1f}m {el:6.1f}d {rng:7.0f}km")
        conn.close()
        return

    horizon_end = start + timedelta(hours=args.hours)
    try:
        with conn.cursor() as cur:
            # Clear the horizon we are about to recompute. Past passes stay:
            # they record what was forecast at the time.
            if args.station:
                cur.execute(
                    "DELETE FROM tracked_pass WHERE station_id = %s "
                    "AND aos_utc >= %s AND aos_utc <= %s",
                    (args.station, start, horizon_end),
                )
            else:
                cur.execute(
                    "DELETE FROM tracked_pass WHERE aos_utc >= %s AND aos_utc <= %s",
                    (start, horizon_end),
                )
            cleared = cur.rowcount

            execute_values(
                cur,
                """
                INSERT INTO tracked_pass
                    (norad_id, station_id, aos_utc, los_utc,
                     max_elevation_deg, range_km_at_max, max_link_score)
                SELECT v.norad_id, v.station_id, v.aos_utc, v.los_utc,
                       v.max_elevation_deg, v.range_km_at_max,
                       -- the radio model lives in SQL, not in this script
                       link_score_from_pass(v.max_elevation_deg, v.range_km_at_max)
                FROM (VALUES %s) AS v (norad_id, station_id, aos_utc, los_utc,
                                       max_elevation_deg, range_km_at_max)
                ON CONFLICT (norad_id, station_id, aos_utc) DO UPDATE SET
                    los_utc           = EXCLUDED.los_utc,
                    max_elevation_deg = EXCLUDED.max_elevation_deg,
                    range_km_at_max   = EXCLUDED.range_km_at_max,
                    max_link_score    = EXCLUDED.max_link_score,
                    computed_at       = now()
                """,
                rows,
                template="(%s, %s, %s::timestamptz, %s::timestamptz, %s::numeric, %s::numeric)",
                page_size=200,
            )
            # NOT cur.rowcount: execute_values sends the rows in pages, so
            # rowcount only reports the final page. Count the horizon instead.
            cur.execute(
                "SELECT count(*) FROM tracked_pass WHERE aos_utc >= %s AND aos_utc <= %s",
                (start, horizon_end),
            )
            written = cur.fetchone()[0]
        conn.commit()
    except psycopg2.errors.InsufficientPrivilege as exc:
        conn.rollback()
        print(f"\n  PERMISSION DENIED as {who} -- PostgreSQL refused it:\n    {exc}")
        conn.close()
        raise SystemExit(1)

    print(f"\n  cleared {cleared} stale forecasts, wrote {written} passes as {who}")

    # Read back through the views, which is what the dashboard will see.
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT object_name, station_name, aos_utc, duration_s,
                   max_elevation_deg, max_link_score, link_grade
            FROM   v_next_passes
            WHERE  station_id = COALESCE(%s, 'KJSSE')
            ORDER  BY aos_utc
            LIMIT  10
            """,
            (args.station,),
        )
        upcoming = cur.fetchall()

        cur.execute(
            """
            SELECT station_id, passes_24h, distinct_objects,
                   avg_max_elevation, best_elevation, contact_minutes
            FROM   v_station_workload
            """
        )
        workload = cur.fetchall()
    conn.close()

    label = args.station or "KJSSE"
    print(f"\n  next real passes over {label} (v_next_passes):")
    print(f"    {'object':22} {'AOS (UTC)':14} {'dur':>6} {'el':>6} {'link':>5}  grade")
    for name, stn, aos, dur, el, score, grade in upcoming:
        print(f"    {name[:22]:22} {aos:%m-%d %H:%M:%S} {dur/60:5.1f}m "
              f"{el:5.1f}d {score:5d}  {grade}")

    print(f"\n  24 h station workload (v_station_workload):")
    print(f"    {'stn':6} {'passes':>7} {'objects':>8} {'avg el':>7} {'best':>6} {'contact':>9}")
    for sid, n, objs, avg_el, best, mins in workload:
        print(f"    {sid:6} {n:>7} {objs:>8} {str(avg_el):>7} {str(best):>6} {mins:>7} min")

    print("\nDone. Next: python scripts/export_stats.py")


if __name__ == "__main__":
    main()
