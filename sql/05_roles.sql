-- ============================================================================
-- SomaiyaSat Ground Control  --  05_roles.sql
-- DCL: CREATE ROLE / GRANT / REVOKE            [Exp 7 - DCL, CO2]
--
-- Three roles, three very different jobs:
--   ground_operator  the mission controller  -> full DML + EXECUTE
--   student_analyst  read-only coursework    -> SELECT on views + telemetry
--   ai_router        the onboard router      -> INSERT telemetry, and that's it
--
-- Passwords and the database name are placeholders; scripts/setup_db.py
-- substitutes them before sending this file to the server, so no secret is
-- ever stored here and the same script works against a hosted database whose
-- name is not ours to choose (Neon hands you "neondb", for example).
--
-- The file is re-runnable: each role is stripped of its privileges with
-- REASSIGN OWNED / DROP OWNED and dropped before being recreated.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Tear down any previous run. DROP ROLE fails while a role still holds
-- privileges or owns objects, so clear those first.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['ground_operator', 'student_analyst', 'ai_router']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            -- hand anything the role owns back to the bootstrap superuser ...
            EXECUTE format('REASSIGN OWNED BY %I TO CURRENT_USER', r);
            -- ... then drop the privileges that were GRANTed to it
            EXECUTE format('DROP OWNED BY %I', r);
            EXECUTE format('DROP ROLE %I', r);
        END IF;
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- Deny by default. PUBLIC is an implicit member of every role, so anything
-- granted to PUBLIC would leak to all three roles below.
-- ---------------------------------------------------------------------------
REVOKE ALL ON DATABASE "__DATABASE__" FROM PUBLIC;
REVOKE ALL ON SCHEMA   public       FROM PUBLIC;
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL PROCEDURES IN SCHEMA public FROM PUBLIC;

CREATE ROLE ground_operator LOGIN PASSWORD '__GROUND_OPERATOR_PASSWORD__';
CREATE ROLE student_analyst LOGIN PASSWORD '__STUDENT_ANALYST_PASSWORD__';
CREATE ROLE ai_router       LOGIN PASSWORD '__AI_ROUTER_PASSWORD__';

-- All three need to reach the database and see the schema.
GRANT CONNECT ON DATABASE "__DATABASE__" TO ground_operator, student_analyst, ai_router;
GRANT USAGE   ON SCHEMA   public       TO ground_operator, student_analyst, ai_router;

-- ===========================================================================
-- ground_operator : mission control. Full DML everywhere + EXECUTE on the
-- routines, so it can confirm deployments and run passes.
-- ===========================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES     IN SCHEMA public TO ground_operator;
GRANT USAGE, SELECT                  ON ALL SEQUENCES  IN SCHEMA public TO ground_operator;
GRANT EXECUTE                        ON ALL FUNCTIONS  IN SCHEMA public TO ground_operator;
GRANT EXECUTE                        ON ALL PROCEDURES IN SCHEMA public TO ground_operator;

-- ===========================================================================
-- student_analyst : coursework account. SELECT on the views and on telemetry.
-- No INSERT / UPDATE / DELETE anywhere, and no EXECUTE, so the Pass Planner's
-- write actions are refused by the server, not hidden by the UI.
-- ===========================================================================
GRANT SELECT ON telemetry TO student_analyst;
GRANT SELECT ON
    v_mission_status,
    v_cube_health,
    v_low_battery_cubes,
    v_pass_ready,
    v_weak_links,
    v_payload_mix
TO student_analyst;

-- Read-only helpers the dashboards need for their dropdowns / charts.
GRANT SELECT ON satellite_cube, ground_pass, payload_priority TO student_analyst;

-- plan_pass is a pure read; let the analyst SEE the router's reasoning.
-- execute_pass is deliberately NOT granted: planning is safe, executing is not.
-- Nor are the index helpers -- the analyst may EXPLAIN, but not reshape the table.
GRANT EXECUTE ON FUNCTION plan_pass(VARCHAR, INT)  TO student_analyst;
GRANT EXECUTE ON FUNCTION pass_budget(INT)         TO student_analyst;

-- ===========================================================================
-- ai_router : the spacecraft's own account. It may push telemetry up and read
-- the routing rules. It may not read anyone's mission status or change a thing.
-- ===========================================================================
GRANT INSERT ON telemetry TO ai_router;
GRANT USAGE  ON SEQUENCE telemetry_packet_id_seq TO ai_router;   -- for SERIAL
GRANT SELECT ON comm_router, payload_priority TO ai_router;

-- ===========================================================================
-- Verify: print the resulting grants so the demo can show them on screen.
-- ===========================================================================
SELECT grantee, table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
FROM   information_schema.role_table_grants
WHERE  grantee IN ('ground_operator', 'student_analyst', 'ai_router')
GROUP  BY grantee, table_name
ORDER  BY grantee, table_name;
