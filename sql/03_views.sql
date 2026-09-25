-- ============================================================================
-- SomaiyaSat Ground Control  --  03_views.sql
-- Views: joins, aggregates, HAVING, nested subqueries, UNION
--   [Exp 6 - Views / Joins / Nested queries, CO3]
--   [Exp 5 - Aggregates, GROUP BY, HAVING, Set operations, CO2]
-- ============================================================================

DROP VIEW IF EXISTS v_payload_mix       CASCADE;
DROP VIEW IF EXISTS v_weak_links        CASCADE;
DROP VIEW IF EXISTS v_pass_ready        CASCADE;
DROP VIEW IF EXISTS v_low_battery_cubes CASCADE;
DROP VIEW IF EXISTS v_cube_health       CASCADE;
DROP VIEW IF EXISTS v_mission_status    CASCADE;

-- ---------------------------------------------------------------------------
-- v_mission_status : the full pod -> cube -> router chain for every satellite.
-- Three-way JOIN. LEFT JOINs so a pod with no cube still shows up.
-- ---------------------------------------------------------------------------
CREATE VIEW v_mission_status AS
SELECT  p.pod_id,
        p.mech_type,
        p.confirm_status,
        p.launch_date,
        c.cube_id,
        c.power_state,
        c.sys_init,
        r.router_id,
        r.link_score,
        r.mode_priorities,
        CASE
            WHEN p.confirm_status = 'Confirmed'
             AND c.sys_init      = 'Complete'
             AND c.power_state  <> 'Critical' THEN 'OPERATIONAL'
            WHEN p.confirm_status = 'Failed'   THEN 'DEPLOY FAILED'
            WHEN p.confirm_status = 'Pending'  THEN 'AWAITING DEPLOYMENT'
            ELSE 'DEGRADED'
        END AS chain_status
FROM        deployer_pod   p
LEFT JOIN   satellite_cube c ON c.pod_id  = p.pod_id
LEFT JOIN   comm_router    r ON r.cube_id = c.cube_id
ORDER BY    p.pod_id;

-- ---------------------------------------------------------------------------
-- v_cube_health : per-cube aggregates over the whole telemetry history.
-- GROUP BY + AVG/MIN/MAX/COUNT, plus a CASE-derived health flag.
--
-- health_flag keys off the LATEST battery reading (a correlated subquery),
-- not the lifetime average, so the dashboard agrees with plan_pass() -- which
-- also routes on the most recent voltage. A cube that started the week healthy
-- and is discharging now should read WARNING today, not be masked by its
-- own good history.
-- ---------------------------------------------------------------------------
CREATE VIEW v_cube_health AS
SELECT  c.cube_id,
        c.power_state,
        COUNT(t.packet_id)                       AS packet_count,
        COUNT(*) FILTER (WHERE NOT t.sent)       AS unsent_count,
        ROUND(AVG(t.battery_voltage), 2)         AS avg_battery,
        MIN(t.battery_voltage)                   AS min_battery,
        MAX(t.battery_voltage)                   AS max_battery,
        (SELECT t2.battery_voltage
           FROM telemetry t2
          WHERE t2.cube_id = c.cube_id
          ORDER BY t2.ts DESC, t2.packet_id DESC
          LIMIT 1)                               AS latest_battery,
        MAX(t.temperature)                       AS max_temp,
        MIN(t.temperature)                       AS min_temp,
        MAX(t.ts)                                AS last_packet_at,
        CASE
            WHEN COUNT(t.packet_id) = 0 THEN 'NO DATA'
            WHEN (SELECT t2.battery_voltage FROM telemetry t2
                   WHERE t2.cube_id = c.cube_id
                   ORDER BY t2.ts DESC, t2.packet_id DESC LIMIT 1) < 6.8
                 THEN 'CRITICAL'
            WHEN (SELECT t2.battery_voltage FROM telemetry t2
                   WHERE t2.cube_id = c.cube_id
                   ORDER BY t2.ts DESC, t2.packet_id DESC LIMIT 1) <= 7.2
                 THEN 'WARNING'
            WHEN MAX(t.temperature) > 42.0 THEN 'THERMAL WATCH'
            ELSE 'HEALTHY'
        END                                      AS health_flag
FROM        satellite_cube c
LEFT JOIN   telemetry      t ON t.cube_id = c.cube_id
GROUP BY    c.cube_id, c.power_state
ORDER BY    c.cube_id;

-- ---------------------------------------------------------------------------
-- v_low_battery_cubes : GROUP BY ... HAVING over the last 24 hours only.
-- These are the cubes the router must protect by dropping SSTV.
-- ---------------------------------------------------------------------------
CREATE VIEW v_low_battery_cubes AS
SELECT  t.cube_id,
        ROUND(AVG(t.battery_voltage), 2) AS avg_battery_24h,
        MIN(t.battery_voltage)           AS min_battery_24h,
        COUNT(*)                         AS packets_24h
FROM        telemetry t
WHERE       t.ts >= now() - INTERVAL '24 hours'
GROUP BY    t.cube_id
HAVING      AVG(t.battery_voltage) < 7.0
ORDER BY    avg_battery_24h;

-- ---------------------------------------------------------------------------
-- v_pass_ready : cubes cleared to be scheduled for a downlink pass.
-- ---------------------------------------------------------------------------
CREATE VIEW v_pass_ready AS
SELECT  c.cube_id,
        c.power_state,
        c.sys_init,
        p.pod_id,
        p.confirm_status,
        r.link_score
FROM        satellite_cube c
JOIN        deployer_pod   p ON p.pod_id  = c.pod_id
LEFT JOIN   comm_router    r ON r.cube_id = c.cube_id
WHERE       p.confirm_status = 'Confirmed'
  AND       c.sys_init       = 'Complete'
  AND       c.power_state   <> 'Critical'
ORDER BY    c.cube_id;

-- ---------------------------------------------------------------------------
-- v_weak_links : routers performing below the fleet average link score.
-- Nested (scalar) subquery in the WHERE clause.
-- ---------------------------------------------------------------------------
CREATE VIEW v_weak_links AS
SELECT  r.router_id,
        r.cube_id,
        r.link_score,
        (SELECT ROUND(AVG(link_score), 1) FROM comm_router) AS fleet_avg_link,
        r.link_score - (SELECT AVG(link_score) FROM comm_router) AS delta_from_avg
FROM        comm_router r
WHERE       r.link_score < (SELECT AVG(link_score) FROM comm_router)
ORDER BY    r.link_score;

-- ---------------------------------------------------------------------------
-- v_payload_mix : volume per payload type, then a UNION that stacks the
-- sent / unsent split underneath as a set operation.
-- ---------------------------------------------------------------------------
CREATE VIEW v_payload_mix AS
    -- Part 1: one row per payload type
    SELECT  pp.payload_type                       AS bucket,
            'BY PAYLOAD TYPE'                     AS bucket_kind,
            pp.priority                           AS priority,
            COUNT(t.packet_id)                    AS packet_count,
            COALESCE(SUM(t.size_bytes), 0)        AS total_bytes
    FROM        payload_priority pp
    LEFT JOIN   telemetry        t ON t.payload_type = pp.payload_type
    GROUP BY    pp.payload_type, pp.priority

    UNION ALL

    -- Part 2: the same packets bucketed by downlink state
    SELECT  CASE WHEN t.sent THEN 'Sent' ELSE 'Unsent (queued)' END,
            'BY DOWNLINK STATE',
            NULL,
            COUNT(*),
            COALESCE(SUM(t.size_bytes), 0)
    FROM        telemetry t
    GROUP BY    t.sent

ORDER BY bucket_kind, priority NULLS LAST, bucket;


-- ===========================================================================
-- REAL TRACKING VIEWS
--
-- The views above summarise the proposed SomaiyaSat mission. These three
-- summarise the real satellites in satellite_tle / tracked_pass.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- v_tracked_fleet : the real satellites we track, with TLE freshness.
--
-- A TLE is a snapshot of an orbit that drifts away from reality over days, so
-- its AGE is the single most important thing about it. A correlated subquery
-- counts each object's upcoming passes.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tracked_fleet AS
SELECT  t.norad_id,
        t.object_name,
        t.payload_modes,
        ROUND(t.inclination_deg, 2)                                   AS inclination_deg,
        ROUND(t.period_min, 1)                                        AS period_min,
        t.eccentricity,
        t.epoch_utc,
        ROUND(EXTRACT(EPOCH FROM (now() - t.epoch_utc)) / 86400.0, 2) AS tle_age_days,
        CASE WHEN now() - t.epoch_utc > INTERVAL '14 days' THEN 'STALE'
             WHEN now() - t.epoch_utc > INTERVAL '7 days'  THEN 'AGEING'
             ELSE                                              'FRESH'
        END                                                           AS tle_status,
        t.source,
        (SELECT count(*) FROM tracked_pass p
          WHERE p.norad_id = t.norad_id AND p.aos_utc > now())        AS upcoming_passes
FROM    satellite_tle t
ORDER BY t.object_name;

-- ---------------------------------------------------------------------------
-- v_next_passes : upcoming REAL passes, soonest first.
--
-- A three-way JOIN (pass -> satellite -> station) with the link grade derived
-- from the very same thresholds plan_pass() applies to the proposed mission.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_next_passes AS
SELECT  p.track_id,
        p.norad_id,
        t.object_name,
        t.payload_modes,
        s.station_id,
        s.name                                              AS station_name,
        s.country                                           AS station_country,
        p.aos_utc,
        p.los_utc,
        EXTRACT(EPOCH FROM (p.los_utc - p.aos_utc))::INT     AS duration_s,
        EXTRACT(EPOCH FROM (p.aos_utc - now()))::INT         AS seconds_until_aos,
        p.max_elevation_deg,
        p.range_km_at_max,
        p.max_link_score,
        CASE WHEN p.max_link_score < 40 THEN 'SAFE MODE - TT&C only'
             WHEN p.max_link_score < 70 THEN 'REDUCED - SSTV at risk'
             ELSE                            'FULL - all modes'
        END                                                  AS link_grade
FROM      tracked_pass   p
JOIN      satellite_tle  t ON t.norad_id   = p.norad_id
JOIN      ground_station s ON s.station_id = p.station_id
WHERE     p.los_utc > now()
ORDER BY  p.aos_utc;

-- ---------------------------------------------------------------------------
-- v_station_workload : how much real contact time each station gets in 24 h.
--
-- LEFT JOIN so a station with no passes still appears with zeros rather than
-- vanishing -- the difference between "no contacts" and "not in the network".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_station_workload AS
SELECT  s.station_id,
        s.name,
        s.country,
        s.is_primary,
        s.min_elevation_deg,
        count(p.track_id)                                    AS passes_24h,
        count(DISTINCT p.norad_id)                           AS distinct_objects,
        ROUND(AVG(p.max_elevation_deg), 1)                   AS avg_max_elevation,
        MAX(p.max_elevation_deg)                             AS best_elevation,
        ROUND(AVG(p.max_link_score), 1)                      AS avg_link_score,
        ROUND(COALESCE(SUM(EXTRACT(EPOCH FROM (p.los_utc - p.aos_utc))), 0) / 60.0, 1)
                                                             AS contact_minutes
FROM      ground_station s
LEFT JOIN tracked_pass   p
       ON p.station_id = s.station_id
      AND p.aos_utc BETWEEN now() AND now() + INTERVAL '24 hours'
GROUP BY  s.station_id, s.name, s.country, s.is_primary, s.min_elevation_deg
ORDER BY  contact_minutes DESC, s.station_id;
