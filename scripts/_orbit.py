"""
Orbital mechanics for the real-tracking feature.

Nothing in here is specific to this project's database -- it is the physics
layer that fetch_tles.py, predict_passes.py and export_stats.py all share.

Two jobs:

  1. Parse the two-line element (TLE) format that CelesTrak publishes.
  2. Propagate an element set with SGP4 and work out where the satellite is,
     and whether a ground station can see it.

SGP4 is the standard propagator for Earth-orbiting objects; TLE sets are only
meaningful when fed through it (you cannot simply read a position out of the
numbers). The `sgp4` package is the reference C++ implementation wrapped for
Python, so the orbits here are as accurate as the published elements allow --
typically a kilometre or so for a fresh LEO element set, degrading over days.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

# WGS-84, the ellipsoid the TLE/SGP4 world uses.
WGS84_A = 6378.137          # equatorial radius, km
WGS84_F = 1 / 298.257223563  # flattening
WGS84_E2 = WGS84_F * (2 - WGS84_F)

# ---------------------------------------------------------------------------
# The tracked fleet.
#
# Chosen from CelesTrak's amateur-radio group because each one is real flight
# heritage for what KJS-SRS-01 proposes -- an amateur-band PocketQube in a
# sun-synchronous-like low Earth orbit.
#
# `modes` uses this project's own payload vocabulary and claims only what is
# well established. Note what is absent: no satellite here has M17 heritage.
# M17 is a recent open digital-voice standard, and that gap is precisely the
# novelty the use case is built on -- it is visible in the data rather than
# merely asserted in the write-up.
# ---------------------------------------------------------------------------
TRACKED_FLEET: dict[str, str] = {
    # ARISS runs genuine slow-scan television transmissions from the ISS, which
    # is the closest flying analogue to SomaiyaSat's SSTV payload.
    "ISS (ZARYA)":       "TT&C, SSTV",
    # LilacSat-2 flew an amateur Codec2 digital-voice transponder -- the direct
    # heritage for the Codec2 mode.
    "LILACSAT-2":        "TT&C, Codec2",
    # Long-running amateur telemetry beacons and transponders.
    "FUNCUBE-1 (AO-73)": "TT&C",
    "SAUDISAT 1C (SO-50)": "TT&C",
    "OSCAR 7 (AO-7)":    "TT&C",
    "EYESAT A (AO-27)":  "TT&C",
    # University CubeSats in the same orbital regime as the proposed mission.
    "UWE-4":             "TT&C",
    "SONATE-2":          "TT&C",
    "MESAT1":            "TT&C",
    "BEESAT-1":          "TT&C",
}

CELESTRAK_GROUPS = ("amateur", "cubesat")
CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"


# ---------------------------------------------------------------------------
# TLE parsing
# ---------------------------------------------------------------------------
def parse_tle_text(text: str) -> list[tuple[str, str, str]]:
    """
    Split a CelesTrak 3-line-per-object file into (name, line1, line2).

    Tolerant of blank lines and of a trailing partial record, because a
    truncated download should yield fewer satellites rather than an exception.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    out: list[tuple[str, str, str]] = []
    i = 0
    while i + 2 < len(lines) + 1:
        if i + 2 >= len(lines) + 1:
            break
        name, l1, l2 = (lines[i] if i < len(lines) else ""), \
                       (lines[i + 1] if i + 1 < len(lines) else ""), \
                       (lines[i + 2] if i + 2 < len(lines) else "")
        if l1.startswith("1 ") and l2.startswith("2 "):
            out.append((name.strip(), l1, l2))
            i += 3
        else:
            i += 1
    return out


def tle_epoch(line1: str) -> datetime:
    """
    The element set's epoch, from columns 19-32 of line 1.

    Format is YYDDD.DDDDDDDD where YY < 57 means 20YY (the convention dates
    from Sputnik, 1957).
    """
    raw = line1[18:32].strip()
    yy = int(raw[:2])
    year = 2000 + yy if yy < 57 else 1900 + yy
    doy = float(raw[2:])
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=doy - 1)


def tle_elements(line2: str) -> dict[str, float]:
    """Inclination, eccentricity and mean motion, read from fixed columns."""
    inclination = float(line2[8:16])
    eccentricity = float("0." + line2[26:33].strip())
    mean_motion = float(line2[52:63])
    period_min = 1440.0 / mean_motion if mean_motion else 0.0
    return {
        "inclination_deg": inclination,
        "eccentricity": eccentricity,
        "mean_motion": mean_motion,
        "period_min": period_min,
    }


def norad_id(line1: str) -> int:
    """Satellite catalogue number, columns 3-7 of line 1."""
    return int(line1[2:7])


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------
def gmst_rad(jd: float, fr: float) -> float:
    """Greenwich mean sidereal time, radians -- how far Earth has turned."""
    d = jd + fr - 2451545.0
    t = d / 36525.0
    deg = 280.46061837 + 360.98564736629 * d + 0.000387933 * t * t
    return math.radians(deg % 360.0)


def teme_to_geodetic(r_km: tuple[float, float, float], jd: float, fr: float
                     ) -> tuple[float, float, float]:
    """
    SGP4's TEME position -> (latitude, longitude, altitude km).

    SGP4 returns coordinates in an inertial frame that does not rotate with the
    Earth, so longitude requires rotating by sidereal time. Latitude needs an
    iteration because the Earth is an ellipsoid, not a sphere.
    """
    theta = gmst_rad(jd, fr)
    x = r_km[0] * math.cos(theta) + r_km[1] * math.sin(theta)
    y = -r_km[0] * math.sin(theta) + r_km[1] * math.cos(theta)
    z = r_km[2]

    lon = math.degrees(math.atan2(y, x))
    lon = (lon + 540.0) % 360.0 - 180.0

    p = math.hypot(x, y)
    lat = math.atan2(z, p)
    for _ in range(8):                       # converges in three or four
        n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
        lat = math.atan2(z + n * WGS84_E2 * math.sin(lat), p)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - n if abs(math.cos(lat)) > 1e-9 else abs(z) - n

    return math.degrees(lat), lon, alt


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_km: float
                     ) -> tuple[float, float, float]:
    """Latitude/longitude/altitude -> Earth-centred, Earth-fixed XYZ in km."""
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(la) ** 2)
    return ((n + alt_km) * math.cos(la) * math.cos(lo),
            (n + alt_km) * math.cos(la) * math.sin(lo),
            (n * (1 - WGS84_E2) + alt_km) * math.sin(la))


def look_angles(st_lat: float, st_lon: float, st_alt_km: float,
                sat_lat: float, sat_lon: float, sat_alt_km: float
                ) -> tuple[float, float]:
    """
    (elevation degrees, slant range km) of a satellite from a ground station.

    Elevation is the angle above the station's local horizon: negative means
    below it and therefore not workable. This is the quantity that defines a
    pass, and it is what the 2000 km ground-distance test in the globe was
    standing in for.
    """
    gx, gy, gz = geodetic_to_ecef(st_lat, st_lon, st_alt_km)
    sx, sy, sz = geodetic_to_ecef(sat_lat, sat_lon, sat_alt_km)
    dx, dy, dz = sx - gx, sy - gy, sz - gz
    rng = math.sqrt(dx * dx + dy * dy + dz * dz)
    if rng == 0:
        return 90.0, 0.0

    la, lo = math.radians(st_lat), math.radians(st_lon)
    ux = math.cos(la) * math.cos(lo)
    uy = math.cos(la) * math.sin(lo)
    uz = math.sin(la)
    sin_el = max(-1.0, min(1.0, (dx * ux + dy * uy + dz * uz) / rng))
    return math.degrees(math.asin(sin_el)), rng


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------
def subpoint(sat: Satrec, when: datetime) -> tuple[float, float, float] | None:
    """Where the satellite is at `when` (UTC): lat, lon, altitude km."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    jd, fr = jday(when.year, when.month, when.day,
                  when.hour, when.minute, when.second + when.microsecond / 1e6)
    err, r, _v = sat.sgp4(jd, fr)
    if err:
        return None                     # decayed, or the elements are unusable
    return teme_to_geodetic(r, jd, fr)


def find_passes(sat: Satrec, st_lat: float, st_lon: float, st_alt_km: float,
                start: datetime, hours: float, min_elevation_deg: float,
                coarse_s: int = 30, fine_s: int = 2) -> list[dict]:
    """
    Every visibility window in [start, start + hours).

    Two-stage search, which is the standard way to do this: step coarsely to
    find where the satellite crosses the horizon mask, then refine each edge so
    the AOS and LOS times are accurate to a couple of seconds. Sampling finely
    across the whole window would be far slower for the same answer.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=hours)

    def elev_at(t: datetime) -> tuple[float, float, float, float, float] | None:
        sp = subpoint(sat, t)
        if sp is None:
            return None
        lat, lon, alt = sp
        el, rng = look_angles(st_lat, st_lon, st_alt_km, lat, lon, alt)
        return el, rng, lat, lon, alt

    # --- coarse scan -------------------------------------------------------
    samples: list[tuple[datetime, tuple]] = []
    t = start
    while t < end:
        v = elev_at(t)
        if v is not None:
            samples.append((t, v))
        t += timedelta(seconds=coarse_s)
    if not samples:
        return []

    def refine(lo: datetime, hi: datetime) -> datetime:
        """Bisect for the horizon crossing between a below and an above sample."""
        for _ in range(24):
            if (hi - lo).total_seconds() <= fine_s:
                break
            mid = lo + (hi - lo) / 2
            v = elev_at(mid)
            if v is None:
                break
            if v[0] < min_elevation_deg:
                lo = mid
            else:
                hi = mid
        return hi

    passes: list[dict] = []
    in_pass = False
    aos: datetime | None = None
    peak: tuple[datetime, tuple] | None = None
    prev: tuple[datetime, tuple] | None = None

    for cur in samples:
        above = cur[1][0] >= min_elevation_deg
        if above and not in_pass:
            in_pass = True
            aos = refine(prev[0], cur[0]) if prev else cur[0]
            peak = cur
        elif above and in_pass:
            if peak is None or cur[1][0] > peak[1][0]:
                peak = cur
        elif not above and in_pass:
            los = refine(cur[0], prev[0]) if prev else cur[0]
            in_pass = False
            if aos and peak and los > aos:
                passes.append(_pass_record(aos, los, peak, sat,
                                           st_lat, st_lon, st_alt_km))
            aos = peak = None
        prev = cur

    # A pass still open when the search window ends: keep it, truncated.
    if in_pass and aos and peak and samples[-1][0] > aos:
        passes.append(_pass_record(aos, samples[-1][0], peak, sat,
                                   st_lat, st_lon, st_alt_km))

    return passes


def _pass_record(aos: datetime, los: datetime, peak: tuple, sat: Satrec,
                 st_lat: float, st_lon: float, st_alt_km: float) -> dict:
    """
    Build one pass row, refining the peak elevation.

    The coarse scan's best sample can be up to half a step away from the true
    maximum, and max elevation drives the link score, so it is worth a short
    local search around it.
    """
    best_t, best = peak[0], peak[1]
    step = timedelta(seconds=8)
    for k in range(-4, 5):
        t = peak[0] + step * k
        if t < aos or t > los:
            continue
        sp = subpoint(sat, t)
        if sp is None:
            continue
        el, rng = look_angles(st_lat, st_lon, st_alt_km, *sp)
        if el > best[0]:
            best_t, best = t, (el, rng, sp[0], sp[1], sp[2])

    return {
        "aos_utc": aos,
        "los_utc": los,
        "tca_utc": best_t,                     # time of closest approach
        "max_elevation_deg": round(best[0], 1),
        "range_km_at_max": round(best[1], 1),
        "duration_s": int((los - aos).total_seconds()),
    }
