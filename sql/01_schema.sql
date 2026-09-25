-- ============================================================================
-- SomaiyaSat Ground Control  --  01_schema.sql
-- DDL: tables, keys, constraints                    [Exp 3 - DDL, CO1]
--
-- Use case KJS-SRS-01: SomaiyaSat (PocketQube) is deployed by SomaiyaPod.
-- An onboard AI router chooses what to downlink during each short ground
-- pass. This schema is the ground-station mirror of that mission state.
-- ============================================================================

-- Idempotent: tear down in reverse dependency order before rebuilding.
DROP TABLE IF EXISTS tracked_pass    CASCADE;
DROP TABLE IF EXISTS satellite_tle   CASCADE;
DROP TABLE IF EXISTS ground_station  CASCADE;
DROP TABLE IF EXISTS deployment_log  CASCADE;
DROP TABLE IF EXISTS ground_pass     CASCADE;
DROP TABLE IF EXISTS telemetry       CASCADE;
DROP TABLE IF EXISTS payload_priority CASCADE;
DROP TABLE IF EXISTS comm_router     CASCADE;
DROP TABLE IF EXISTS satellite_cube  CASCADE;
DROP TABLE IF EXISTS deployer_pod    CASCADE;

-- ---------------------------------------------------------------------------
-- deployer_pod : the SomaiyaPod deployer that ejects the PocketQube
-- ---------------------------------------------------------------------------
CREATE TABLE deployer_pod (
    pod_id         VARCHAR(10)  PRIMARY KEY,
    mech_type      VARCHAR(30)  NOT NULL,
    confirm_status VARCHAR(20)  NOT NULL
                   CHECK (confirm_status IN ('Pending', 'Confirmed', 'Failed')),
    launch_date    DATE
);

-- ---------------------------------------------------------------------------
-- satellite_cube : the PocketQube itself. One cube per pod (1:1 via UNIQUE FK)
-- ---------------------------------------------------------------------------
CREATE TABLE satellite_cube (
    cube_id     VARCHAR(10) PRIMARY KEY,
    power_state VARCHAR(20) CHECK (power_state IN ('Nominal', 'Low', 'Critical', 'Idle')),
    sys_init    VARCHAR(20) CHECK (sys_init IN ('Standby', 'Complete', 'Failed')),
    pod_id      VARCHAR(10) UNIQUE REFERENCES deployer_pod(pod_id)
);

-- ---------------------------------------------------------------------------
-- comm_router : the onboard AI router. link_score is the modelled RF quality
-- of the upcoming pass (0-100). One router per cube (1:1 via UNIQUE FK).
-- ---------------------------------------------------------------------------
CREATE TABLE comm_router (
    router_id       VARCHAR(10) PRIMARY KEY,
    link_score      INT         CHECK (link_score BETWEEN 0 AND 100),
    mode_priorities VARCHAR(50),
    cube_id         VARCHAR(10) UNIQUE REFERENCES satellite_cube(cube_id)
);

-- ---------------------------------------------------------------------------
-- payload_priority : lookup table that encodes the mission rule
--   TT&C  >  SSTV  >  M17  >  Codec2
-- Kept as DATA (not hard-coded in the app) so the router rule is auditable.
-- ---------------------------------------------------------------------------
CREATE TABLE payload_priority (
    payload_type VARCHAR(30) PRIMARY KEY,
    priority     INT  NOT NULL CHECK (priority > 0),
    description  VARCHAR(120)
);

-- ---------------------------------------------------------------------------
-- telemetry : every packet the satellite has buffered. sent = FALSE means it
-- is still sitting in the downlink queue waiting for a pass.
-- ---------------------------------------------------------------------------
CREATE TABLE telemetry (
    packet_id       SERIAL PRIMARY KEY,
    cube_id         VARCHAR(10) REFERENCES satellite_cube(cube_id),
    payload_type    VARCHAR(30)
                    CHECK (payload_type IN ('TT&C', 'SSTV', 'M17', 'Codec2')),
    battery_voltage NUMERIC(4,2),
    temperature     NUMERIC(5,2),
    size_bytes      INT CHECK (size_bytes > 0),
    ts              TIMESTAMP NOT NULL,
    sent            BOOLEAN DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- ground_pass : a visibility window over the Somaiya ground station.
-- max_link_score is the predicted peak link quality for that window.
-- ---------------------------------------------------------------------------
CREATE TABLE ground_pass (
    pass_id        SERIAL PRIMARY KEY,
    cube_id        VARCHAR(10) REFERENCES satellite_cube(cube_id),
    start_time     TIMESTAMP,
    end_time       TIMESTAMP,
    max_link_score INT CHECK (max_link_score BETWEEN 0 AND 100),
    CONSTRAINT chk_pass_window CHECK (end_time > start_time)
);

-- ---------------------------------------------------------------------------
-- deployment_log : audit trail for deployment attempts, including the ones
-- that were rolled back (see confirm_deployment in 04_functions.sql).
-- ---------------------------------------------------------------------------
CREATE TABLE deployment_log (
    log_id    SERIAL PRIMARY KEY,
    pod_id    VARCHAR(10),
    cube_id   VARCHAR(10),
    action    VARCHAR(50),
    outcome   VARCHAR(20),
    logged_at TIMESTAMP DEFAULT now()
);


-- ===========================================================================
-- REAL SATELLITE TRACKING
--
-- Everything above models the PROPOSED SomaiyaSat mission. The three tables
-- below hold real orbital data for satellites that are actually in orbit now.
--
-- Why both: SomaiyaSat has not launched, so it has no orbit to track. A real
-- mission validates its ground segment against satellites already flying
-- before its own launch, and that is exactly what these tables let the
-- dashboard do -- the same link-budget reasoning, run over real pass windows.
--
-- Note the timestamp type changes here: TIMESTAMPTZ, not TIMESTAMP. Orbital
-- mechanics is done in UTC, and storing UTC instants in a naive TIMESTAMP
-- column on a server running in IST would silently shift every pass by 5h30m.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ground_station : the ground segment, as data.
--
-- These six sites previously existed only as a Python literal in
-- scripts/export_stats.py, duplicated again in landing/src/hooks/useStats.ts.
-- Real pass prediction needs a station's latitude, longitude, altitude and
-- horizon mask, so the list belongs in the database and is now read from here.
-- ---------------------------------------------------------------------------
CREATE TABLE ground_station (
    station_id        VARCHAR(10)  PRIMARY KEY,
    name              VARCHAR(60)  NOT NULL,
    country           VARCHAR(60),
    latitude          NUMERIC(8,5) NOT NULL CHECK (latitude  BETWEEN  -90 AND  90),
    longitude         NUMERIC(9,5) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    altitude_m        INT          NOT NULL DEFAULT 0,
    -- A pass is only usable once the satellite clears local obstructions.
    -- 10 degrees is the usual amateur-station rule of thumb.
    min_elevation_deg NUMERIC(4,1) NOT NULL DEFAULT 10.0
                      CHECK (min_elevation_deg BETWEEN 0 AND 90),
    is_primary        BOOLEAN      NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- satellite_tle : real two-line element sets, fetched from CelesTrak.
--
-- norad_id is the natural key assigned by US Space Command, which is what
-- makes a re-fetch an UPSERT (INSERT ... ON CONFLICT DO UPDATE) rather than a
-- duplicate -- see scripts/fetch_tles.py.
--
-- The TLE lines are stored verbatim as CHAR(69) because the format is
-- column-positional: character 19-32 is the epoch, 9-16 on line 2 is the
-- inclination, and so on. Trimming or reformatting them breaks the propagator.
-- ---------------------------------------------------------------------------
CREATE TABLE satellite_tle (
    norad_id        INT          PRIMARY KEY,
    object_name     VARCHAR(60)  NOT NULL,
    tle_line1       CHAR(69)     NOT NULL,
    tle_line2       CHAR(69)     NOT NULL,
    epoch_utc       TIMESTAMPTZ  NOT NULL,
    inclination_deg NUMERIC(6,3),
    mean_motion     NUMERIC(12,8),          -- revolutions per day
    period_min      NUMERIC(8,3),           -- 1440 / mean_motion
    eccentricity    NUMERIC(9,7),
    -- Which of our four payload modes this satellite actually flies. This is
    -- why these particular birds were chosen: they are the flight heritage
    -- behind the modes KJS-SRS-01 proposes.
    payload_modes   VARCHAR(60),
    source          VARCHAR(40)  NOT NULL DEFAULT 'celestrak:amateur',
    fetched_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_tle_line1 CHECK (tle_line1 LIKE '1 %'),
    CONSTRAINT chk_tle_line2 CHECK (tle_line2 LIKE '2 %')
);

-- ---------------------------------------------------------------------------
-- tracked_pass : a REAL visibility window, computed by SGP4.
--
-- One row per (satellite, station, pass). Compare with ground_pass above,
-- which holds the proposed mission's windows: that table has no station
-- column because it implicitly means "over Somaiya", and no elevation because
-- its link scores were authored rather than computed. Here both are real.
--
-- The UNIQUE constraint is what makes re-running the predictor idempotent:
-- recomputing the same window updates it instead of inserting a duplicate.
-- ---------------------------------------------------------------------------
CREATE TABLE tracked_pass (
    track_id          SERIAL       PRIMARY KEY,
    norad_id          INT          NOT NULL REFERENCES satellite_tle(norad_id)  ON DELETE CASCADE,
    station_id        VARCHAR(10)  NOT NULL REFERENCES ground_station(station_id) ON DELETE CASCADE,
    aos_utc           TIMESTAMPTZ  NOT NULL,   -- acquisition of signal
    los_utc           TIMESTAMPTZ  NOT NULL,   -- loss of signal
    max_elevation_deg NUMERIC(4,1) NOT NULL CHECK (max_elevation_deg BETWEEN 0 AND 90),
    range_km_at_max   NUMERIC(8,1),
    -- Derived from the two columns above by link_score_from_pass(), so it is
    -- on the same 0-100 scale as comm_router.link_score and can drive the
    -- very same safe-mode rule in plan_pass().
    max_link_score    INT          NOT NULL CHECK (max_link_score BETWEEN 0 AND 100),
    computed_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_track_window CHECK (los_utc > aos_utc),
    CONSTRAINT uq_tracked_pass  UNIQUE (norad_id, station_id, aos_utc)
);
