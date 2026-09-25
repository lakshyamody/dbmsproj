#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- export mission stats for the UI.

Reads the existing views (v_mission_status, v_cube_health, ground_pass,
telemetry) and writes stats.json. This script is READ-ONLY: it never creates,
alters or writes to the database.

If PostgreSQL or .env is unreachable it writes realistic mock data with exactly
the same shape, so the landing page and the globe never crash without a DB.
Every payload carries `"source": "database" | "mock"` so the UI can say which.

    python scripts/export_stats.py [--out DIR ...] [--mock]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTS = [
    ROOT / "landing" / "public" / "data",
    ROOT / "landing" / "dist" / "data",
    ROOT / "app" / "data",
]

PAYLOAD_ORDER = ["TT&C", "SSTV", "M17", "Codec2"]

# Ground station network. KJSSE Mumbai is the primary; ReOrbit's Helsinki site
# is the collaborating station. The rest give the globe a plausible network.
STATIONS = [
    {"id": "KJSSE",  "name": "KJSSE Mumbai",  "country": "India",       "lat": 19.07, "lng": 72.90, "primary": True},
    {"id": "HEL",    "name": "Helsinki",      "country": "Finland",     "lat": 60.17, "lng": 24.94, "primary": True},
    {"id": "SVAL",   "name": "Svalbard",      "country": "Norway",      "lat": 78.22, "lng": 15.65, "primary": False},
    {"id": "BLR",    "name": "Bengaluru",     "country": "India",       "lat": 12.97, "lng": 77.59, "primary": False},
    {"id": "SGP",    "name": "Singapore",     "country": "Singapore",   "lat": 1.35,  "lng": 103.82, "primary": False},
    {"id": "SNT",    "name": "Santiago",      "country": "Chile",       "lat": -33.45, "lng": -70.67, "primary": False},
]


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def link_band(score: int) -> str:
    return "good" if score >= 70 else ("fair" if score >= 40 else "poor")


# ---------------------------------------------------------------------------
# database path
# ---------------------------------------------------------------------------
def from_database(conn=None) -> dict:
    """
    Build the whole payload from the database.

    `conn` lets a caller supply its own connection instead of opening one. The
    dashboard uses that to build this payload live, as the logged-in role, so a
    deployed instance is not stuck serving whatever stats.json happened to be
    committed -- element sets age and pass windows expire, so a file baked at
    build time stops being true within a day. A borrowed connection is left
    open for its owner to manage.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _conn

    borrowed = conn is not None
    if conn is None:
        conn = _conn.connect(connect_timeout=8)

    def rows(sql, params=None):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    try:
        mission = rows("SELECT * FROM v_mission_status")
        health = rows("SELECT * FROM v_cube_health")
        payloads = rows(
            """
            SELECT pp.payload_type, pp.priority, pp.description,
                   count(t.packet_id)                  AS packet_count,
                   count(t.packet_id) FILTER (WHERE NOT t.sent) AS unsent_count,
                   COALESCE(sum(t.size_bytes), 0)      AS total_bytes
            FROM   payload_priority pp
            LEFT JOIN telemetry t ON t.payload_type = pp.payload_type
            GROUP  BY pp.payload_type, pp.priority, pp.description
            ORDER  BY pp.priority
            """
        )
        passes = rows(
            """
            SELECT pass_id, cube_id, start_time, end_time, max_link_score,
                   EXTRACT(EPOCH FROM (end_time - start_time))::int AS duration_s
            FROM   ground_pass
            ORDER  BY start_time
            """
        )
        totals = rows(
            """
            SELECT (SELECT count(*) FROM telemetry)                    AS packets,
                   (SELECT count(*) FROM telemetry WHERE NOT sent)     AS unsent,
                   (SELECT count(*) FROM ground_pass)                  AS passes,
                   (SELECT count(*) FROM satellite_cube)               AS cubes,
                   (SELECT count(*) FROM deployer_pod)                 AS pods,
                   (SELECT COALESCE(sum(size_bytes),0) FROM telemetry) AS bytes
            """
        )[0]
        # 24h battery sparkline, hourly, per cube
        spark = rows(
            """
            SELECT cube_id,
                   date_trunc('hour', ts) AS hour,
                   round(avg(battery_voltage), 3)::float8 AS v
            FROM   telemetry
            WHERE  ts >= now() - interval '24 hours'
            GROUP  BY cube_id, date_trunc('hour', ts)
            ORDER  BY cube_id, hour
            """
        )

        # ------------------------------------------------------------ real data
        # The tracked fleet: real satellites with their element sets, so the
        # globe can propagate them in the browser using the same SGP4 the
        # database used. Nothing here is invented -- see scripts/fetch_tles.py.
        tracked = rows(
            """
            SELECT t.norad_id, t.object_name, t.payload_modes, t.tle_line1,
                   t.tle_line2, t.epoch_utc, t.inclination_deg, t.period_min,
                   f.tle_age_days, f.tle_status,
                   (SELECT p.aos_utc FROM tracked_pass p
                     WHERE p.norad_id = t.norad_id AND p.station_id = 'KJSSE'
                       AND p.los_utc > now() ORDER BY p.aos_utc LIMIT 1) AS next_aos,
                   (SELECT p.max_link_score FROM tracked_pass p
                     WHERE p.norad_id = t.norad_id AND p.station_id = 'KJSSE'
                       AND p.los_utc > now() ORDER BY p.aos_utc LIMIT 1) AS next_link
            FROM   satellite_tle t
            JOIN   v_tracked_fleet f ON f.norad_id = t.norad_id
            ORDER  BY t.object_name
            """
        )

        tracked_passes = rows(
            """
            SELECT track_id, norad_id, object_name, station_id, station_name,
                   aos_utc, los_utc, duration_s, max_elevation_deg,
                   range_km_at_max, max_link_score, link_grade
            FROM   v_next_passes
            ORDER  BY aos_utc
            LIMIT  60
            """
        )

        # Ground stations now live in the database (they used to be a literal
        # in this file). Real pass prediction needs their coordinates and
        # horizon masks, so they are data, and this is where the UI reads them.
        station_rows = rows(
            """
            SELECT station_id, name, country, latitude, longitude, altitude_m,
                   min_elevation_deg, is_primary
            FROM   ground_station
            -- KJSSE leads: it is the mission's own station, so it is the one
            -- the globe centres on and the one the UI treats as "home".
            -- Sorting on is_primary alone would put Helsinki first (both are
            -- primary, and 'HEL' < 'KJSSE').
            ORDER  BY (station_id = 'KJSSE') DESC, is_primary DESC, station_id
            """
        )
    finally:
        if not borrowed:
            conn.close()

    stations = [{
        "id": s["station_id"],
        "name": s["name"],
        "country": s["country"],
        "lat": float(s["latitude"]),
        "lng": float(s["longitude"]),
        "alt_m": int(s["altitude_m"]),
        "min_elevation_deg": float(s["min_elevation_deg"]),
        "primary": bool(s["is_primary"]),
    } for s in station_rows] or STATIONS

    by_cube_health = {h["cube_id"]: h for h in health}
    spark_by_cube: dict[str, list[float]] = {}
    for r in spark:
        spark_by_cube.setdefault(r["cube_id"], []).append(round(float(r["v"]), 3))

    now = datetime.now(timezone.utc)
    sats = []
    for m in mission:
        cube = m.get("cube_id")
        if not cube:
            continue
        h = by_cube_health.get(cube, {})
        series = spark_by_cube.get(cube, [])
        latest = h.get("latest_battery")
        latest = float(latest) if latest is not None else (series[-1] if series else None)
        upcoming = [p for p in passes if p["cube_id"] == cube
                    and p["start_time"].replace(tzinfo=timezone.utc) > now]
        score = int(m.get("link_score") or 0)
        sats.append({
            "cube_id": cube,
            "pod_id": m.get("pod_id"),
            "mech_type": m.get("mech_type"),
            "confirm_status": m.get("confirm_status"),
            "launch_date": m["launch_date"].isoformat() if m.get("launch_date") else None,
            "power_state": m.get("power_state"),
            "sys_init": m.get("sys_init"),
            "router_id": m.get("router_id"),
            "link_score": score,
            "link_band": link_band(score),
            "chain_status": m.get("chain_status"),
            "health_flag": h.get("health_flag"),
            "packet_count": int(h.get("packet_count") or 0),
            "unsent_count": int(h.get("unsent_count") or 0),
            "battery_latest": round(latest, 2) if latest is not None else None,
            "battery_avg": float(h["avg_battery"]) if h.get("avg_battery") is not None else None,
            "battery_min": float(h["min_battery"]) if h.get("min_battery") is not None else None,
            "battery_24h": series[-24:],
            "battery_24h_ago": series[0] if series else None,
            "temp_max": float(h["max_temp"]) if h.get("max_temp") is not None else None,
            "temp_min": float(h["min_temp"]) if h.get("min_temp") is not None else None,
            "last_packet_at": iso(h["last_packet_at"]) if h.get("last_packet_at") else None,
            "next_pass": iso(upcoming[0]["start_time"]) if upcoming else None,
            "next_pass_id": upcoming[0]["pass_id"] if upcoming else None,
            "deployed": m.get("confirm_status") == "Confirmed" and m.get("sys_init") == "Complete",
        })

    return {
        "source": "database",
        "generated_at": iso(now),
        "satellites": sats,
        "payloads": [{
            "payload_type": p["payload_type"],
            "priority": int(p["priority"]),
            "description": p["description"],
            "packet_count": int(p["packet_count"]),
            "unsent_count": int(p["unsent_count"]),
            "total_bytes": int(p["total_bytes"]),
        } for p in payloads],
        "passes": [{
            "pass_id": p["pass_id"],
            "cube_id": p["cube_id"],
            "start_time": iso(p["start_time"]),
            "end_time": iso(p["end_time"]),
            "max_link_score": int(p["max_link_score"] or 0),
            "duration_s": int(p["duration_s"] or 0),
        } for p in passes],
        "stations": stations,
        # Real satellites, kept in their own key so nothing that reads
        # `satellites` can confuse a tracked object with the proposed mission.
        "tracked": [{
            "norad_id": int(t["norad_id"]),
            "object_name": t["object_name"],
            "payload_modes": t["payload_modes"],
            "tle_line1": t["tle_line1"].strip(),
            "tle_line2": t["tle_line2"].strip(),
            "epoch_utc": iso(t["epoch_utc"]),
            "inclination_deg": float(t["inclination_deg"] or 0),
            "period_min": float(t["period_min"] or 0),
            "tle_age_days": float(t["tle_age_days"] or 0),
            "tle_status": t["tle_status"],
            "next_aos": iso(t["next_aos"]) if t.get("next_aos") else None,
            "next_link": int(t["next_link"]) if t.get("next_link") is not None else None,
        } for t in tracked],
        "tracked_passes": [{
            "track_id": int(p["track_id"]),
            "norad_id": int(p["norad_id"]),
            "object_name": p["object_name"],
            "station_id": p["station_id"],
            "station_name": p["station_name"],
            "aos_utc": iso(p["aos_utc"]),
            "los_utc": iso(p["los_utc"]),
            "duration_s": int(p["duration_s"] or 0),
            "max_elevation_deg": float(p["max_elevation_deg"] or 0),
            "range_km_at_max": float(p["range_km_at_max"] or 0),
            "max_link_score": int(p["max_link_score"] or 0),
            "link_grade": p["link_grade"],
        } for p in tracked_passes],
        "totals": {
            "satellites": int(totals["cubes"]),
            "deployed_satellites": sum(1 for s in sats if s["deployed"]),
            "pods": int(totals["pods"]),
            "packets": int(totals["packets"]),
            "unsent_packets": int(totals["unsent"]),
            "passes": int(totals["passes"]),
            "payload_modes": len(payloads),
            "total_bytes": int(totals["bytes"]),
            "ground_stations": len(stations),
            "tracked_objects": len(tracked),
            "tracked_passes": len(tracked_passes),
        },
    }


# ---------------------------------------------------------------------------
# mock path -- identical shape, no database required
# ---------------------------------------------------------------------------
def from_mock() -> dict:
    rng = random.Random(20260923)
    now = datetime.now(timezone.utc)

    spec = [
        {"cube_id": "CUBE01", "pod_id": "POD01", "volts": 7.80, "link": 85,
         "power_state": "Nominal", "health_flag": "HEALTHY",
         "mech_type": "Spring-Loaded Rail", "launch": "2026-01-14"},
        {"cube_id": "CUBE02", "pod_id": "POD02", "volts": 6.80, "link": 70,
         "power_state": "Low", "health_flag": "WARNING",
         "mech_type": "Spring-Loaded Rail", "launch": "2026-01-14"},
        {"cube_id": "CUBE03", "pod_id": "POD03", "volts": 7.60, "link": 30,
         "power_state": "Nominal", "health_flag": "THERMAL WATCH",
         "mech_type": "Pusher Plate", "launch": "2026-02-02"},
    ]

    total_packets = 4998
    per_cube = total_packets // 3
    # Same mix the generator uses: TT&C dominates by count, SSTV by volume.
    mix = {"TT&C": 0.50, "SSTV": 0.15, "M17": 0.20, "Codec2": 0.15}
    avg_bytes = {"TT&C": 160, "SSTV": 46000, "M17": 2560, "Codec2": 2560}

    sats, passes = [], []
    pass_id = 1
    for i, s in enumerate(spec):
        # 24 hourly readings drifting toward the pinned latest value
        series = []
        for h in range(24):
            f = h / 23
            base = s["volts"] + (0.34 if s["cube_id"] == "CUBE02" else 0.12) * (1 - f)
            series.append(round(base + rng.gauss(0, 0.02), 3))
        series[-1] = s["volts"]

        my_passes = []
        for k in range(3):
            start = now + timedelta(hours=2 + i + 12 * k, minutes=rng.randint(0, 40))
            dur = rng.randint(360, 600)
            score = max(0, min(100, s["link"] + rng.randint(-6, 4)))
            my_passes.append({
                "pass_id": pass_id, "cube_id": s["cube_id"],
                "start_time": iso(start), "end_time": iso(start + timedelta(seconds=dur)),
                "max_link_score": score, "duration_s": dur,
            })
            pass_id += 1
        passes.extend(my_passes)

        unsent = int(per_cube * 0.20)
        sats.append({
            "cube_id": s["cube_id"],
            "pod_id": s["pod_id"],
            "mech_type": s["mech_type"],
            "confirm_status": "Confirmed",
            "launch_date": s["launch"],
            "power_state": s["power_state"],
            "sys_init": "Complete",
            "router_id": f"RTR0{i + 1}",
            "link_score": s["link"],
            "link_band": link_band(s["link"]),
            "chain_status": "OPERATIONAL",
            "health_flag": s["health_flag"],
            "packet_count": per_cube,
            "unsent_count": unsent,
            "battery_latest": s["volts"],
            "battery_avg": round(sum(series) / len(series), 2),
            "battery_min": round(min(series), 2),
            "battery_24h": series,
            "battery_24h_ago": series[0],
            "temp_max": round(rng.uniform(38, 45), 2),
            "temp_min": round(rng.uniform(20, 25), 2),
            "last_packet_at": iso(now - timedelta(minutes=rng.randint(1, 20))),
            "next_pass": my_passes[0]["start_time"],
            "next_pass_id": my_passes[0]["pass_id"],
            "deployed": True,
        })

    payloads = []
    for idx, ptype in enumerate(PAYLOAD_ORDER):
        count = int(total_packets * mix[ptype])
        payloads.append({
            "payload_type": ptype,
            "priority": idx + 1,
            "description": {
                "TT&C": "Telemetry, tracking & command housekeeping - never dropped",
                "SSTV": "Slow-scan TV imagery - large frames, power hungry",
                "M17": "M17 digital voice / data",
                "Codec2": "Codec2 low-bitrate voice",
            }[ptype],
            "packet_count": count,
            "unsent_count": int(count * 0.20),
            "total_bytes": int(count * avg_bytes[ptype]),
        })

    return {
        "source": "mock",
        "generated_at": iso(now),
        "satellites": sats,
        "payloads": payloads,
        "passes": passes,
        "stations": STATIONS,
        # Deliberately empty, not faked. Real orbital data cannot be invented:
        # a made-up TLE would propagate to a real-looking position that is
        # simply wrong. Without a database the globe shows the proposed mission
        # only, and the tracking panel says so.
        "tracked": [],
        "tracked_passes": [],
        "totals": {
            "satellites": 4,
            "deployed_satellites": 3,
            "pods": 4,
            "packets": total_packets,
            "unsent_packets": sum(p["unsent_count"] for p in payloads),
            "passes": len(passes),
            "payload_modes": len(payloads),
            "total_bytes": sum(p["total_bytes"] for p in payloads),
            "ground_stations": len(STATIONS),
            "tracked_objects": 0,
            "tracked_passes": 0,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", action="append", default=None,
                    help="output directory (repeatable); defaults to landing + app")
    ap.add_argument("--mock", action="store_true", help="skip the database entirely")
    args = ap.parse_args()

    if args.mock:
        stats, note = from_mock(), "forced mock data"
    else:
        try:
            stats, note = from_database(), "live database"
        except Exception as exc:
            first = str(exc).strip().splitlines()[0][:120]
            print(f"  database unavailable ({first})")
            stats, note = from_mock(), "mock fallback"

    outs = [Path(o) for o in args.out] if args.out else DEFAULT_OUTS
    written = 0
    for d in outs:
        # dist/ only exists after a build; skip it rather than creating a stray dir
        if d.name == "data" and d.parent.name == "dist" and not d.parent.exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
        print(f"  wrote {(d / 'stats.json')}")
        written += 1

    t = stats["totals"]
    print(f"\n  source: {note}")
    print(f"  {t['satellites']} satellites · {t['packets']:,} packets · "
          f"{t['passes']} passes · {t['payload_modes']} payload modes · "
          f"{t['ground_stations']} ground stations")
    if written == 0:
        print("  (no output directories existed)", file=sys.stderr)


if __name__ == "__main__":
    main()
