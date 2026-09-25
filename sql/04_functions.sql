-- ============================================================================
-- SomaiyaSat Ground Control  --  04_functions.sql
-- PL/pgSQL procedures & functions
--   [Exp 9 - TCL: COMMIT / ROLLBACK / SAVEPOINT, CO1 & CO4]
--   [Exp 6 - Window functions & nested queries, CO3]
--
-- This file holds the rule-based fallback router that use case KJS-SRS-01
-- asks for: deterministic, auditable, and explainable in plain English.
-- ============================================================================

-- ===========================================================================
-- 1. confirm_deployment  --  TRANSACTION DEMO (COMMIT / ROLLBACK)
-- ===========================================================================
-- The whole body runs inside ONE transaction (the caller's). Either every
-- statement lands or none of them do.
--
-- When p_simulate_failure is TRUE the procedure raises partway through, AFTER
-- the pod has already been updated. That UPDATE is discarded by the rollback,
-- which is exactly the point of the demo.
--
-- IMPORTANT: the failed attempt must still be recorded. An INSERT made here
-- would be rolled back along with everything else, so the audit row CANNOT be
-- written inside this procedure. The caller catches the exception, issues a
-- ROLLBACK, and then calls log_deployment_attempt() in a FRESH transaction.
-- See confirm_deployment() in app/db.py.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE confirm_deployment(
    p_pod_id           VARCHAR(10),
    p_simulate_failure BOOLEAN DEFAULT FALSE
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cube_id VARCHAR(10);
    v_status  VARCHAR(20);
BEGIN
    SELECT p.confirm_status INTO v_status
    FROM   deployer_pod p WHERE p.pod_id = p_pod_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pod % does not exist', p_pod_id
            USING ERRCODE = 'no_data_found';
    END IF;

    SELECT c.cube_id INTO v_cube_id
    FROM   satellite_cube c WHERE c.pod_id = p_pod_id;

    IF v_cube_id IS NULL THEN
        RAISE EXCEPTION 'Pod % has no satellite cube attached', p_pod_id
            USING ERRCODE = 'no_data_found';
    END IF;

    -- ---- step 1 of 3 : mark the deployer confirmed -------------------------
    UPDATE deployer_pod
       SET confirm_status = 'Confirmed',
           launch_date    = CURRENT_DATE
     WHERE pod_id = p_pod_id;

    -- ---- fault injection : everything above is now un-done by the rollback -
    IF p_simulate_failure THEN
        RAISE EXCEPTION
            'SIMULATED FAILURE: separation switch on pod % never latched, deployment aborted',
            p_pod_id
            USING ERRCODE = 'P0001';
    END IF;

    -- ---- step 2 of 3 : bring the cube out of standby ------------------------
    UPDATE satellite_cube
       SET sys_init    = 'Complete',
           power_state = 'Nominal'
     WHERE cube_id = v_cube_id;

    -- ---- step 3 of 3 : audit the success -----------------------------------
    INSERT INTO deployment_log (pod_id, cube_id, action, outcome)
    VALUES (p_pod_id, v_cube_id, 'CONFIRM_DEPLOYMENT', 'SUCCESS');
END;
$$;


-- ---------------------------------------------------------------------------
-- log_deployment_attempt : called by the app AFTER a rollback, in its own
-- transaction, so the failed attempt survives in the audit trail.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION log_deployment_attempt(
    p_pod_id  VARCHAR(10),
    p_action  VARCHAR(50),
    p_outcome VARCHAR(20)
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_cube_id VARCHAR(10);
    v_log_id  INT;
BEGIN
    SELECT c.cube_id INTO v_cube_id
    FROM   satellite_cube c WHERE c.pod_id = p_pod_id;

    INSERT INTO deployment_log (pod_id, cube_id, action, outcome)
    VALUES (p_pod_id, v_cube_id, p_action, p_outcome)
    RETURNING log_id INTO v_log_id;

    RETURN v_log_id;
END;
$$;


-- ---------------------------------------------------------------------------
-- reset_deployment_demo : puts POD04/CUBE04 back to un-deployed so the
-- rollback demo can be replayed during a viva.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE reset_deployment_demo()
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE deployer_pod
       SET confirm_status = 'Pending', launch_date = NULL
     WHERE pod_id = 'POD04';

    UPDATE satellite_cube
       SET sys_init = 'Standby', power_state = 'Idle'
     WHERE cube_id = 'CUBE04';

    INSERT INTO deployment_log (pod_id, cube_id, action, outcome)
    VALUES ('POD04', 'CUBE04', 'RESET_DEMO', 'SUCCESS');
END;
$$;


-- ===========================================================================
-- 2. plan_pass  --  THE RULE-BASED FALLBACK ROUTER
-- ===========================================================================
-- Deterministic replacement for the onboard AI router. Given a cube and one
-- of its upcoming passes it returns the full downlink queue, in order, with a
-- TRANSMIT / DEFER / SKIP decision and a plain-English reason for every row.
--
-- Rules, in the order they are applied:
--   budget_bytes = pass_duration_seconds * (max_link_score * 12)
--   R1  latest battery < 6.8 V  OR  link_score < 40   -> TT&C is the only
--       eligible payload (safe mode)
--   R2  latest battery between 6.8 V and 7.2 V        -> TT&C + M17 + Codec2;
--       SSTV is dropped because imaging is the most power-hungry mode
--   R3  otherwise                                     -> everything eligible
--
-- Eligible packets are ordered by payload priority then timestamp, and a
-- running SUM() OVER (ORDER BY ...) window function gives cumulative bytes.
-- Rows that fit the budget are TRANSMIT, the rest are DEFER. Payload types
-- excluded by R1/R2 come back as SKIP so the operator can see what was left
-- behind and why -- the explainability requirement from KJS-SRS-01.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION plan_pass(
    p_cube_id VARCHAR(10),
    p_pass_id INT
)
RETURNS TABLE (
    queue_pos        INT,
    packet_id        INT,
    payload_type     VARCHAR(30),
    size_bytes       INT,
    cumulative_bytes BIGINT,
    decision         VARCHAR(10),
    reason           TEXT
)
LANGUAGE plpgsql
STABLE
-- SECURITY DEFINER: runs with the owner's rights, so student_analyst can see
-- the router's REASONING without being granted SELECT on comm_router itself.
-- Safe here because the function only reads and takes no dynamic SQL; the
-- pinned search_path stops anyone shadowing our tables with a temp one.
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    v_start      TIMESTAMP;
    v_end        TIMESTAMP;
    v_max_link   INT;
    v_duration_s NUMERIC;
    v_budget     BIGINT;
    v_battery    NUMERIC(4,2);
    v_link       INT;
    v_eligible   TEXT[];
    v_skip_tail  TEXT;
    v_conditions TEXT;
BEGIN
    -- ---- the pass window ---------------------------------------------------
    SELECT g.start_time, g.end_time, g.max_link_score
      INTO v_start, v_end, v_max_link
      FROM ground_pass g
     WHERE g.pass_id = p_pass_id AND g.cube_id = p_cube_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pass % does not belong to cube %', p_pass_id, p_cube_id
            USING ERRCODE = 'no_data_found';
    END IF;

    v_duration_s := EXTRACT(EPOCH FROM (v_end - v_start));
    v_budget     := FLOOR(v_duration_s * (v_max_link * 12))::BIGINT;

    -- ---- current spacecraft state -----------------------------------------
    -- Latest battery reading = most recent telemetry row for this cube.
    SELECT t.battery_voltage INTO v_battery
      FROM telemetry t
     WHERE t.cube_id = p_cube_id
     ORDER BY t.ts DESC, t.packet_id DESC
     LIMIT 1;

    SELECT r.link_score INTO v_link
      FROM comm_router r WHERE r.cube_id = p_cube_id;

    v_link := COALESCE(v_link, 0);

    -- ---- rule selection ----------------------------------------------------
    IF v_battery IS NULL THEN
        -- No telemetry at all: fall back to the safest possible behaviour.
        v_eligible  := ARRAY['TT&C'];
        v_skip_tail := 'safe mode - no telemetry on record for this cube, '
                    || 'so only housekeeping is cleared for downlink';

    ELSIF v_battery < 6.8 OR v_link < 40 THEN
        -- R1: safe mode, housekeeping only.
        v_conditions := '';
        IF v_battery < 6.8 THEN
            v_conditions := format('battery %sV below the 6.8V floor', v_battery);
        END IF;
        IF v_link < 40 THEN
            IF v_conditions <> '' THEN
                v_conditions := v_conditions || ' and ';
            END IF;
            v_conditions := v_conditions
                         || format('link score %s below the 40 minimum', v_link);
        END IF;

        v_eligible  := ARRAY['TT&C'];
        v_skip_tail := format('safe mode, TT&C only (%s)', v_conditions);

    ELSIF v_battery <= 7.2 THEN
        -- R2: caution band, drop imaging only.
        v_eligible  := ARRAY['TT&C', 'M17', 'Codec2'];
        v_skip_tail := format(
            'battery %sV below 7.2V threshold (SSTV is the most power-hungry mode)',
            v_battery);

    ELSE
        -- R3: all clear.
        v_eligible  := ARRAY['TT&C', 'SSTV', 'M17', 'Codec2'];
        v_skip_tail := 'not eligible';
    END IF;

    -- ---- build the queue ---------------------------------------------------
    RETURN QUERY
    WITH queued AS (
        -- every packet still waiting in the downlink buffer, with its priority
        SELECT  t.packet_id    AS pid,
                t.payload_type AS ptype,
                t.size_bytes   AS sz,
                t.ts           AS pts,
                pp.priority    AS prio
        FROM        telemetry        t
        JOIN        payload_priority pp ON pp.payload_type = t.payload_type
        WHERE       t.cube_id = p_cube_id
          AND       t.sent    = FALSE
    ),
    eligible AS (
        -- WINDOW FUNCTION: running total of bytes down the priority-ordered queue
        SELECT  q.pid, q.ptype, q.sz, q.prio,
                ROW_NUMBER() OVER (ORDER BY q.prio, q.pts, q.pid) AS pos,
                SUM(q.sz)    OVER (ORDER BY q.prio, q.pts, q.pid
                                   ROWS BETWEEN UNBOUNDED PRECEDING
                                            AND CURRENT ROW)      AS cum
        FROM        queued q
        WHERE       q.ptype = ANY (v_eligible)
    ),
    skipped AS (
        -- payload types the rules excluded; numbered after the eligible queue
        SELECT  q.pid, q.ptype, q.sz, q.prio,
                (SELECT COUNT(*) FROM eligible)
                  + ROW_NUMBER() OVER (ORDER BY q.prio, q.pts, q.pid) AS pos
        FROM        queued q
        WHERE       NOT (q.ptype = ANY (v_eligible))
    )
    SELECT  e.pos::INT,
            e.pid,
            e.ptype::VARCHAR(30),
            e.sz,
            e.cum::BIGINT,
            (CASE WHEN e.cum <= v_budget THEN 'TRANSMIT' ELSE 'DEFER' END)::VARCHAR(10),
            CASE
                WHEN e.cum <= v_budget THEN
                    format('Transmit: priority %s payload, %s of %s byte budget used',
                           e.prio, e.cum, v_budget)
                ELSE
                    format('Deferred: pass budget of %s bytes exceeded (queue reaches %s bytes here)',
                           v_budget, e.cum)
            END
    FROM eligible e

    UNION ALL

    SELECT  s.pos::INT,
            s.pid,
            s.ptype::VARCHAR(30),
            s.sz,
            NULL::BIGINT,
            'SKIP'::VARCHAR(10),
            s.ptype || ' skipped: ' || v_skip_tail
    FROM skipped s

    ORDER BY 1;
END;
$$;


-- ---------------------------------------------------------------------------
-- pass_budget : small helper so the UI can show the budget and the inputs
-- that produced it without re-deriving the arithmetic in Python.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pass_budget(p_pass_id INT)
RETURNS TABLE (
    duration_seconds INT,
    max_link_score   INT,
    bytes_per_second INT,
    budget_bytes     BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT  EXTRACT(EPOCH FROM (g.end_time - g.start_time))::INT,
            g.max_link_score,
            (g.max_link_score * 12)::INT,
            FLOOR(EXTRACT(EPOCH FROM (g.end_time - g.start_time))
                  * (g.max_link_score * 12))::BIGINT
    FROM    ground_pass g
    WHERE   g.pass_id = p_pass_id;
$$;


-- ===========================================================================
-- 3. execute_pass  --  SAVEPOINT DEMO
-- ===========================================================================
-- Commits the plan produced by plan_pass() by flipping sent = TRUE.
--
-- The mission rule is that housekeeping must never be lost. So the work is
-- split into two stages:
--
--   STAGE 1  mark the TT&C packets sent.
--   SAVEPOINT
--   STAGE 2  mark SSTV / M17 / Codec2 sent.
--
-- In PL/pgSQL a `BEGIN ... EXCEPTION ... END` block IS a savepoint: Postgres
-- opens an internal subtransaction on entry and, if anything inside raises,
-- rolls back TO THAT POINT and runs the handler. Stage 1 therefore survives
-- even when stage 2 blows up -- which is what p_simulate_failure demonstrates.
--
-- (Bare SAVEPOINT / ROLLBACK TO statements are not valid inside PL/pgSQL;
--  the exception block is the supported way to express the same thing.)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION execute_pass(
    p_cube_id          VARCHAR(10),
    p_pass_id          INT,
    p_simulate_failure BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    stage          TEXT,
    packets_marked INT,
    bytes_marked   BIGINT,
    status         TEXT,
    note           TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_ttc_ids   INT[];
    v_other_ids INT[];
    v_count     INT;
    v_bytes     BIGINT;
BEGIN
    -- Snapshot the plan ONCE. Re-calling plan_pass() after stage 1 would see
    -- the TT&C packets already sent and silently re-flow the whole budget.
    SELECT  COALESCE(array_agg(pp.packet_id) FILTER (WHERE pp.payload_type = 'TT&C'),  '{}'),
            COALESCE(array_agg(pp.packet_id) FILTER (WHERE pp.payload_type <> 'TT&C'), '{}')
      INTO  v_ttc_ids, v_other_ids
      FROM  plan_pass(p_cube_id, p_pass_id) pp
     WHERE  pp.decision = 'TRANSMIT';

    -- ================= STAGE 1 : TT&C, before the savepoint =================
    WITH upd AS (
        UPDATE telemetry t
           SET sent = TRUE
         WHERE t.packet_id = ANY (v_ttc_ids)
        RETURNING t.size_bytes
    )
    SELECT COUNT(*)::INT, COALESCE(SUM(upd.size_bytes), 0)::BIGINT
      INTO v_count, v_bytes
      FROM upd;

    stage          := '1. TT&C housekeeping (before SAVEPOINT)';
    packets_marked := v_count;
    bytes_marked   := v_bytes;
    status         := 'COMMITTED';
    note           := 'Highest priority. Protected from any stage-2 failure.';
    RETURN NEXT;

    -- ======================= SAVEPOINT sp_after_ttc =========================
    -- Entering this block opens the subtransaction. Anything that raises
    -- inside it unwinds only back to here, never past it.
    BEGIN
        WITH upd AS (
            UPDATE telemetry t
               SET sent = TRUE
             WHERE t.packet_id = ANY (v_other_ids)
            RETURNING t.size_bytes
        )
        SELECT COUNT(*)::INT, COALESCE(SUM(upd.size_bytes), 0)::BIGINT
          INTO v_count, v_bytes
          FROM upd;

        -- fault injection for the demo
        IF p_simulate_failure THEN
            RAISE EXCEPTION
                'SIMULATED FAILURE: downlink dropped mid-pass while streaming payload data'
                USING ERRCODE = 'P0001';
        END IF;

        stage          := '2. SSTV / M17 / Codec2 (after SAVEPOINT)';
        packets_marked := v_count;
        bytes_marked   := v_bytes;
        status         := 'COMMITTED';
        note           := 'Payload data downlinked successfully.';

    EXCEPTION WHEN OTHERS THEN
        -- ROLLBACK TO SAVEPOINT sp_after_ttc happened implicitly right here.
        -- Stage 1's UPDATE is untouched and will still be committed.
        stage          := '2. SSTV / M17 / Codec2 (after SAVEPOINT)';
        packets_marked := 0;
        bytes_marked   := 0;
        status         := 'ROLLED BACK TO SAVEPOINT';
        note           := 'Rolled back to sp_after_ttc: ' || SQLERRM
                       || ' -- TT&C from stage 1 survives.';
    END;

    RETURN NEXT;
END;
$$;


-- ===========================================================================
-- 4. Index benchmark helpers                    [Exp 8 - Indexing, CO3]
-- ===========================================================================
-- CREATE INDEX / DROP INDEX require ownership of the table, and ground_operator
-- deliberately only has DML -- it does not own telemetry. These two wrappers are
-- SECURITY DEFINER, so they run with the owner's rights, and EXECUTE on them is
-- granted only to ground_operator. student_analyst is refused, which is the
-- behaviour the Index Benchmark page demonstrates.
--
-- KEEP IN SYNC with sql/06_indexes.sql -- that file is the readable reference
-- the benchmark page displays and that you can run by hand in psql. These
-- wrappers exist so the app can apply the same DDL without handing the operator
-- role ownership of the table.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bench_create_indexes()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_telemetry_cube_ts      ON telemetry (cube_id, ts);
    CREATE INDEX IF NOT EXISTS idx_telemetry_payload_type ON telemetry (payload_type);
    ANALYZE telemetry;
    RETURN 'created idx_telemetry_cube_ts, idx_telemetry_payload_type';
END;
$$;

CREATE OR REPLACE FUNCTION bench_drop_indexes()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    DROP INDEX IF EXISTS idx_telemetry_cube_ts;
    DROP INDEX IF EXISTS idx_telemetry_payload_type;
    ANALYZE telemetry;
    RETURN 'dropped idx_telemetry_cube_ts, idx_telemetry_payload_type';
END;
$$;

-- ---------------------------------------------------------------------------
-- bench_bulk_load : adds N synthetic packets so the benchmark has enough rows
-- for the planner to prefer an index scan. Also SECURITY DEFINER so it can
-- ANALYZE afterwards.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bench_bulk_load(p_rows INT DEFAULT 200000)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_inserted BIGINT;
BEGIN
    INSERT INTO telemetry
        (cube_id, payload_type, battery_voltage, temperature, size_bytes, ts, sent)
    SELECT  ('CUBE0' || (1 + (g % 3)))::VARCHAR(10),
            (ARRAY['TT&C','SSTV','M17','Codec2'])[1 + (g % 4)],
            ROUND((7.00 + (g % 120) / 100.0)::NUMERIC, 2),
            ROUND((20 + (g % 25))::NUMERIC, 2),
            64 + (g % 40000),
            now() - ((g % 604800) || ' seconds')::INTERVAL,
            (g % 5) <> 0
    FROM    generate_series(1, p_rows) AS g;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    ANALYZE telemetry;
    RETURN v_inserted;
END;
$$;


-- ===========================================================================
-- link_score_from_pass : real pass geometry -> the 0-100 link score the rest
-- of the schema already speaks.
--
-- ground_pass.max_link_score was authored by hand for the proposed mission.
-- For a REAL pass we can compute it, because the two things that dominate a
-- LEO amateur link are both measurable from the pass geometry:
--
--   1. Free-space path loss rises with the square of slant range. In decibels
--      that is 20*log10(range / 500 km), taking 500 km as the reference for a
--      typical LEO satellite passing overhead.
--
--   2. Near the horizon the signal crosses much more atmosphere and is far
--      more likely to be blocked by buildings or terrain. Atmospheric air mass
--      goes as 1/sin(elevation), and the excess loss is modelled as
--      10*log10(1 / sin(elevation)) dB.
--
-- The two losses are summed and mapped linearly onto 0-100 across a 30 dB
-- span. That calibration is deliberate: it places a marginal 10-degree pass
-- just above the 40-point safe-mode threshold used by plan_pass(), and drops
-- anything lower into safe mode -- so the rule that was invented for the demo
-- turns out to trigger on exactly the passes a real operator would distrust.
--
-- IMMUTABLE: same inputs always give the same score, so the planner may
-- inline it and it is safe in an index or a generated column.
-- ===========================================================================
CREATE OR REPLACE FUNCTION link_score_from_pass(
    p_max_elevation_deg NUMERIC,
    p_range_km          NUMERIC
)
RETURNS INT
LANGUAGE sql
IMMUTABLE
AS $$
    -- The ::NUMERIC casts are required, not cosmetic: PostgreSQL's two-argument
    -- log(base, x) is defined for NUMERIC, while sin() and radians() return
    -- DOUBLE PRECISION, so the air-mass term has to be cast back.
    SELECT GREATEST(0, LEAST(100, ROUND(
        100 - (
              -- free-space path loss, dB relative to a 500 km overhead pass
              20 * log(10, (GREATEST(COALESCE(p_range_km, 500), 1) / 500.0)::NUMERIC)
              -- excess atmospheric / obstruction loss near the horizon, dB
            + 10 * log(10, (1 / GREATEST(
                                sin(radians(GREATEST(COALESCE(p_max_elevation_deg, 0), 1.0)::FLOAT8)),
                                0.01))::NUMERIC)
        ) * (100.0 / 30.0)
    )))::INT;
$$;


-- ===========================================================================
-- next_tracked_pass : the next real pass for one satellite over one station.
--
-- A small convenience wrapper the Live Tracking page uses for its countdown.
-- STABLE rather than IMMUTABLE because it reads tables and depends on now().
-- ===========================================================================
CREATE OR REPLACE FUNCTION next_tracked_pass(
    p_norad_id   INT,
    p_station_id VARCHAR(10) DEFAULT 'KJSSE'
)
RETURNS TABLE (
    track_id          INT,
    aos_utc           TIMESTAMPTZ,
    los_utc           TIMESTAMPTZ,
    seconds_until_aos INT,
    duration_s        INT,
    max_elevation_deg NUMERIC(4,1),
    max_link_score    INT
)
LANGUAGE sql
STABLE
AS $$
    SELECT  p.track_id,
            p.aos_utc,
            p.los_utc,
            EXTRACT(EPOCH FROM (p.aos_utc - now()))::INT,
            EXTRACT(EPOCH FROM (p.los_utc - p.aos_utc))::INT,
            p.max_elevation_deg,
            p.max_link_score
    FROM    tracked_pass p
    WHERE   p.norad_id   = p_norad_id
      AND   p.station_id = p_station_id
      AND   p.los_utc    > now()
    ORDER BY p.aos_utc
    LIMIT 1;
$$;
