-- ============================================================================
-- SomaiyaSat Ground Control  --  02_seed.sql
-- DML: fixed seed data                              [Exp 4 - DML, CO1]
--
-- Four mission chains, each engineered to show a different router decision:
--   POD01/CUBE01 : healthy, strong link  -> everything is eligible
--   POD02/CUBE02 : low battery           -> SSTV gets dropped
--   POD03/CUBE03 : poor link (30)        -> TT&C only
--   POD04/CUBE04 : not deployed yet      -> used for the transaction demo
-- ============================================================================

TRUNCATE deployment_log, ground_pass, telemetry, payload_priority,
         comm_router, satellite_cube, deployer_pod RESTART IDENTITY CASCADE;

-- --------------------------------------------------------------------- pods
INSERT INTO deployer_pod (pod_id, mech_type, confirm_status, launch_date) VALUES
    ('POD01', 'Spring-Loaded Rail', 'Confirmed', DATE '2026-01-14'),
    ('POD02', 'Spring-Loaded Rail', 'Confirmed', DATE '2026-01-14'),
    ('POD03', 'Pusher Plate',       'Confirmed', DATE '2026-02-02'),
    ('POD04', 'Pusher Plate',       'Pending',   NULL);

-- -------------------------------------------------------------------- cubes
INSERT INTO satellite_cube (cube_id, power_state, sys_init, pod_id) VALUES
    ('CUBE01', 'Nominal',  'Complete', 'POD01'),
    ('CUBE02', 'Low',      'Complete', 'POD02'),
    ('CUBE03', 'Nominal',  'Complete', 'POD03'),
    ('CUBE04', 'Idle',     'Standby',  'POD04');

-- ------------------------------------------------------------------ routers
-- mode_priorities records the router's configured preference order.
INSERT INTO comm_router (router_id, link_score, mode_priorities, cube_id) VALUES
    ('RTR01', 85, 'TT&C>SSTV>M17>Codec2', 'CUBE01'),
    ('RTR02', 70, 'TT&C>SSTV>M17>Codec2', 'CUBE02'),
    ('RTR03', 30, 'TT&C>SSTV>M17>Codec2', 'CUBE03'),
    ('RTR04', 55, 'TT&C>SSTV>M17>Codec2', 'CUBE04');

-- --------------------------------------------------------- payload priority
INSERT INTO payload_priority (payload_type, priority, description) VALUES
    ('TT&C',   1, 'Telemetry, tracking & command housekeeping - never dropped'),
    ('SSTV',   2, 'Slow-scan TV imagery - large frames, power hungry'),
    ('M17',    3, 'M17 digital voice / data'),
    ('Codec2', 4, 'Codec2 low-bitrate voice');

-- -------------------------------------------------------------- ground pass
-- Upcoming windows, relative to now() so the demo never goes stale.
-- Each is 6-10 minutes long; max_link_score tracks the router's link_score.
INSERT INTO ground_pass (cube_id, start_time, end_time, max_link_score) VALUES
    ('CUBE01', now() + INTERVAL '2 hours',  now() + INTERVAL '2 hours 8 minutes',  85),
    ('CUBE01', now() + INTERVAL '14 hours', now() + INTERVAL '14 hours 10 minutes', 78),
    ('CUBE01', now() + INTERVAL '26 hours', now() + INTERVAL '26 hours 6 minutes',  81),

    ('CUBE02', now() + INTERVAL '3 hours',  now() + INTERVAL '3 hours 9 minutes',   70),
    ('CUBE02', now() + INTERVAL '15 hours', now() + INTERVAL '15 hours 7 minutes',  66),
    ('CUBE02', now() + INTERVAL '27 hours', now() + INTERVAL '27 hours 10 minutes', 72),

    ('CUBE03', now() + INTERVAL '4 hours',  now() + INTERVAL '4 hours 10 minutes',  30),
    ('CUBE03', now() + INTERVAL '16 hours', now() + INTERVAL '16 hours 6 minutes',  28),
    ('CUBE03', now() + INTERVAL '28 hours', now() + INTERVAL '28 hours 8 minutes',  34);

-- CUBE04 has no pass: it has not been deployed yet.

-- ------------------------------------------------------------ initial audit
INSERT INTO deployment_log (pod_id, cube_id, action, outcome) VALUES
    ('POD01', 'CUBE01', 'CONFIRM_DEPLOYMENT', 'SUCCESS'),
    ('POD02', 'CUBE02', 'CONFIRM_DEPLOYMENT', 'SUCCESS'),
    ('POD03', 'CUBE03', 'CONFIRM_DEPLOYMENT', 'SUCCESS');
