-- ============================================================================
-- SomaiyaSat Ground Control  --  01_schema.sql
-- DDL: tables, keys, constraints                    [Exp 3 - DDL, CO1]
--
-- Use case KJS-SRS-01: SomaiyaSat (PocketQube) is deployed by SomaiyaPod.
-- An onboard AI router chooses what to downlink during each short ground
-- pass. This schema is the ground-station mirror of that mission state.
-- ============================================================================

-- Idempotent: tear down in reverse dependency order before rebuilding.
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
