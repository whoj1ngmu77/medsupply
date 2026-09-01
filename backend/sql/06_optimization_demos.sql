-- Four rewrite pairs demonstrating optimizer behaviour.
-- Run each pair and compare plans.

\echo '=========== A. SELECTION PUSHDOWN ==========='
\echo '--- A1: filter applied AFTER the join'
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM (
    SELECT b.batch_id, b.qty_on_hand, m.name, m.criticality
    FROM inventory_batch b JOIN medicine m ON m.medicine_id = b.medicine_id
) sub
WHERE sub.criticality = 'LIFE_SAVING';

\echo '--- A2: filter pushed BEFORE the join'
EXPLAIN (ANALYZE, BUFFERS)
SELECT b.batch_id, b.qty_on_hand, m.name, m.criticality
FROM medicine m JOIN inventory_batch b ON b.medicine_id = m.medicine_id
WHERE m.criticality = 'LIFE_SAVING';

\echo ''
\echo '=========== B. PROJECTION PUSHDOWN ==========='
\echo '--- B1: SELECT *'
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM inventory_batch WHERE medicine_id = 12;

\echo '--- B2: only the needed columns (index-only scan candidate)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT batch_id, expiry_date FROM inventory_batch WHERE medicine_id = 12;

\echo ''
\echo '=========== C. JOIN ORDERING ==========='
\echo '--- C1: planner free to choose'
EXPLAIN (ANALYZE, BUFFERS)
SELECT h.name, COUNT(*)
FROM emergency_request r
JOIN hospital h ON h.hospital_id = r.hospital_id
JOIN medicine m ON m.medicine_id = r.medicine_id
WHERE m.criticality = 'LIFE_SAVING' AND r.priority = 'CRITICAL'
GROUP BY h.name;

\echo '--- C2: join order forced (join_collapse_limit = 1)'
SET join_collapse_limit = 1;
EXPLAIN (ANALYZE, BUFFERS)
SELECT h.name, COUNT(*)
FROM emergency_request r
JOIN hospital h ON h.hospital_id = r.hospital_id
JOIN medicine m ON m.medicine_id = r.medicine_id
WHERE m.criticality = 'LIFE_SAVING' AND r.priority = 'CRITICAL'
GROUP BY h.name;
RESET join_collapse_limit;

\echo ''
\echo '=========== D. INDEX SCAN vs SEQ SCAN ==========='
\echo '--- D1: selective predicate (index expected)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM inventory_batch WHERE warehouse_id = 5 AND medicine_id = 12;

\echo '--- D2: index disabled by force'
SET enable_indexscan = off;
SET enable_bitmapscan = off;
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM inventory_batch WHERE warehouse_id = 5 AND medicine_id = 12;
RESET enable_indexscan;
RESET enable_bitmapscan;

\echo '--- D3: unselective predicate — seq scan is CORRECT here'
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM inventory_batch WHERE qty_on_hand > 0;
