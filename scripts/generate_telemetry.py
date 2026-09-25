#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- telemetry generator.

Inserts ~5000 realistic packets over the last 7 days for CUBE01..CUBE03.

Connects as the `ai_router` role on purpose: that role is granted INSERT on
telemetry and nothing else, so a successful run is itself a DCL demo. Counting
the result needs SELECT, so the summary is read back as the superuser.
Use --as-superuser to skip the ai_router hop.

The three cubes are tuned so the Pass Planner shows three different outcomes:

    CUBE01  battery ends ~7.80 V, link 85  ->  every payload type eligible
    CUBE02  battery ends  6.90 V, link 70  ->  SSTV dropped (6.8-7.2 V band)
    CUBE03  battery ends ~7.60 V, link 30  ->  safe mode, TT&C only

The final reading of each cube is pinned to a fixed value because plan_pass()
keys off the MOST RECENT battery row; leaving it to chance would make the demo
flip between rules from run to run.

    python scripts/generate_telemetry.py [--packets 5000] [--as-superuser]
"""
from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE", "space_deploy")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")
AI_ROUTER_PASSWORD = os.getenv("AI_ROUTER_PASSWORD", "router123")

SEED = 20260923
DAYS = 7

# payload_type -> (min_bytes, max_bytes, share of the packet mix)
PAYLOADS = {
    "TT&C":   (64,    256,   0.50),
    "SSTV":   (30720, 61440, 0.15),
    "M17":    (1024,  4096,  0.20),
    "Codec2": (1024,  4096,  0.15),
}

# cube -> battery start V, battery end V, temp band, pinned final reading
CUBES = {
    "CUBE01": {"v_start": 8.10, "v_end": 7.80, "temp": (20.0, 39.0), "v_final": 7.80},
    "CUBE02": {"v_start": 7.60, "v_end": 6.90, "temp": (24.0, 41.0), "v_final": 6.90},
    "CUBE03": {"v_start": 8.00, "v_end": 7.60, "temp": (22.0, 45.0), "v_final": 7.60},
}


def pick_payload(rng: random.Random) -> str:
    return rng.choices(list(PAYLOADS), weights=[p[2] for p in PAYLOADS.values()], k=1)[0]


def build_rows(total: int) -> list[tuple]:
    rng = random.Random(SEED)
    now = datetime.now().replace(microsecond=0)
    window_start = now - timedelta(days=DAYS)
    span = (now - window_start).total_seconds()

    per_cube = total // len(CUBES)
    rows: list[tuple] = []

    for cube_id, cfg in CUBES.items():
        cube_rows = []
        for i in range(per_cube):
            # f = 0.0 at the oldest packet, 1.0 at the newest
            f = (i + 1) / per_cube
            ts = window_start + timedelta(seconds=f * span + rng.uniform(-90, 90))
            ts = min(max(ts, window_start), now)

            # Battery follows the cube's discharge trend plus a little noise,
            # and dips slightly during eclipse (modelled as a sine over the day).
            trend = cfg["v_start"] + (cfg["v_end"] - cfg["v_start"]) * f
            noise = rng.gauss(0, 0.05)
            eclipse = -0.06 if (ts.hour % 12) < 4 else 0.0
            voltage = round(min(8.20, max(6.50, trend + noise + eclipse)), 2)

            t_lo, t_hi = cfg["temp"]
            temperature = round(rng.uniform(t_lo, t_hi), 2)

            payload = pick_payload(rng)
            lo, hi = PAYLOADS[payload][:2]
            size_bytes = rng.randint(lo, hi)

            # Old packets have long since been downlinked; the recent tail is
            # still queued. Works out to roughly 20% unsent overall.
            unsent_p = 0.05 if f < 0.70 else 0.55
            sent = rng.random() >= unsent_p

            cube_rows.append([cube_id, payload, voltage, temperature, size_bytes, ts, sent])

        cube_rows.sort(key=lambda r: r[5])

        # Pin the newest reading so plan_pass() always picks the intended rule,
        # and make sure the newest packet is housekeeping (it is the one the
        # operator sees as "last contact").
        cube_rows[-1][2] = cfg["v_final"]
        cube_rows[-1][1] = "TT&C"
        cube_rows[-1][4] = rng.randint(64, 256)

        rows.extend(tuple(r) for r in cube_rows)

    return rows


def connect(user: str, password: str):
    return psycopg2.connect(
        host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=user, password=password
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packets", type=int, default=5000)
    ap.add_argument("--as-superuser", action="store_true",
                    help="insert as PGUSER instead of the ai_router role")
    ap.add_argument("--keep", action="store_true",
                    help="append instead of clearing existing telemetry first")
    args = ap.parse_args()

    rows = build_rows(args.packets)

    if not args.keep:
        # ai_router has no DELETE, so the wipe is done by the superuser.
        with connect(PGUSER, PGPASSWORD) as admin:
            with admin.cursor() as cur:
                cur.execute("DELETE FROM telemetry")
            admin.commit()
        print("  cleared existing telemetry")

    if args.as_superuser:
        user, password, label = PGUSER, PGPASSWORD, PGUSER
    else:
        user, password, label = "ai_router", AI_ROUTER_PASSWORD, "ai_router (INSERT-only role)"

    try:
        conn = connect(user, password)
    except psycopg2.OperationalError as exc:
        print(f"  could not connect as {user}: {exc}")
        print("  falling back to the superuser")
        conn, label = connect(PGUSER, PGPASSWORD), PGUSER

    with conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """INSERT INTO telemetry
                   (cube_id, payload_type, battery_voltage, temperature, size_bytes, ts, sent)
                   VALUES %s""",
                rows,
                page_size=1000,
            )
    conn.close()
    print(f"  inserted {len(rows)} packets as {label}")

    # Read back as the superuser: ai_router has no SELECT on telemetry.
    with connect(PGUSER, PGPASSWORD) as admin:
        with admin.cursor() as cur:
            cur.execute(
                """
                SELECT cube_id,
                       count(*),
                       count(*) FILTER (WHERE NOT sent),
                       round(avg(battery_voltage), 2),
                       min(battery_voltage),
                       (SELECT t2.battery_voltage FROM telemetry t2
                         WHERE t2.cube_id = t.cube_id
                         ORDER BY t2.ts DESC, t2.packet_id DESC LIMIT 1)
                FROM   telemetry t
                GROUP  BY cube_id ORDER BY cube_id
                """
            )
            print(f"\n  {'cube':<8}{'packets':>9}{'unsent':>8}{'avg V':>8}{'min V':>8}{'latest V':>10}")
            for cube, n, unsent, avg_v, min_v, latest in cur.fetchall():
                print(f"  {cube:<8}{n:>9}{unsent:>8}{avg_v:>8}{min_v:>8}{latest:>10}")

    print("\nDone. Next: streamlit run app/Home.py")


if __name__ == "__main__":
    main()
