-- ============================================================================
-- SomaiyaSat Ground Control  --  06_indexes.sql
-- Indexing                                     [Exp 8 - Indexing, CO3]
--
-- NOT run by setup_db.py. The Index Benchmark page applies this file at
-- runtime so the before/after EXPLAIN ANALYZE comparison is visible live.
--
-- The query being tuned is the Telemetry Log's main filter:
--     SELECT ... FROM telemetry
--     WHERE cube_id = ? AND ts BETWEEN ? AND ? AND payload_type = ?
-- ============================================================================

-- Composite B-tree. Column order matters: cube_id is an equality predicate so
-- it leads, and ts is a range predicate so it follows. That lets one index
-- serve both the equality lookup and the range scan, and also serves queries
-- that filter on cube_id alone (leftmost-prefix rule).
CREATE INDEX IF NOT EXISTS idx_telemetry_cube_ts
    ON telemetry (cube_id, ts);

-- Low-cardinality helper: only four payload types, so on its own this is a
-- poor filter, but the planner can combine it with the index above via a
-- bitmap AND when both predicates are selective enough.
CREATE INDEX IF NOT EXISTS idx_telemetry_payload_type
    ON telemetry (payload_type);

-- Refresh statistics so the planner costs the new indexes correctly.
ANALYZE telemetry;
