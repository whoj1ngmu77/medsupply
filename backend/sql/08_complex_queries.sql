-- Complex SQL showcase. Each query demonstrates a distinct feature.
-- Run: psql "$PGPASS" -f backend/sql/08_complex_queries.sql

\echo '=== C1: Correlated subquery — hospitals above their city average ==='
SELECT h.name, h.city, h.bed_capacity,
       (SELECT ROUND(AVG(h2.bed_capacity))
        FROM hospital h2 WHERE h2.city = h.city) AS city_avg
FROM hospital h
WHERE h.bed_capacity > (
    SELECT AVG(h2.bed_capacity) FROM hospital h2 WHERE h2.city = h.city)
ORDER BY h.city, h.bed_capacity DESC
LIMIT 10;

\echo ''
\echo '=== C2: Window functions — rank within category ==='
SELECT category_name, medicine_name, available,
       RANK() OVER (PARTITION BY category_name ORDER BY available DESC) AS rank_in_cat,
       ROUND(100.0 * available / SUM(available) OVER (PARTITION BY category_name), 1)
           AS pct_of_category
FROM (
    SELECT c.name AS category_name, m.name AS medicine_name,
           COALESCE(SUM(b.qty_on_hand - b.qty_reserved), 0) AS available
    FROM medicine_category c
    JOIN medicine m ON m.category_id = c.category_id
    LEFT JOIN inventory_batch b ON b.medicine_id = m.medicine_id
                               AND b.expiry_date > CURRENT_DATE
    GROUP BY c.name, m.name
) t
WHERE available > 0
ORDER BY category_name, rank_in_cat
LIMIT 20;

\echo ''
\echo '=== C3: Division — hospitals requesting EVERY life-saving medicine ==='
SELECT h.hospital_id, h.name, h.city
FROM hospital h
WHERE NOT EXISTS (
    SELECT m.medicine_id FROM medicine m
    WHERE m.criticality = 'LIFE_SAVING'
      AND NOT EXISTS (
          SELECT 1 FROM emergency_request r
          WHERE r.hospital_id = h.hospital_id
            AND r.medicine_id = m.medicine_id))
LIMIT 10;

\echo ''
\echo '=== C4: Set difference — medicines requested but never supplied ==='
SELECT m.medicine_id, m.name, m.criticality
FROM medicine m
WHERE m.medicine_id IN (
    SELECT medicine_id FROM emergency_request
    EXCEPT
    SELECT medicine_id FROM supply_consignment);

\echo ''
\echo '=== C5: Recursive CTE — expiry cohort buckets ==='
WITH RECURSIVE buckets(lo, hi) AS (
    SELECT 0, 30
    UNION ALL
    SELECT hi, hi + 30 FROM buckets WHERE hi < 180
)
SELECT b.lo || '-' || b.hi || ' days' AS window,
       COUNT(ib.batch_id) AS batches,
       COALESCE(SUM(ib.qty_on_hand - ib.qty_reserved), 0) AS units
FROM buckets b
LEFT JOIN inventory_batch ib
       ON ib.expiry_date > CURRENT_DATE + b.lo
      AND ib.expiry_date <= CURRENT_DATE + b.hi
GROUP BY b.lo, b.hi
ORDER BY b.lo;

\echo ''
\echo '=== C6: LATERAL join — top 2 batches per medicine ==='
SELECT m.name AS medicine, t.batch_number, t.qty_available, t.expiry_date
FROM medicine m
CROSS JOIN LATERAL (
    SELECT b.batch_number, b.qty_on_hand - b.qty_reserved AS qty_available,
           b.expiry_date
    FROM inventory_batch b
    WHERE b.medicine_id = m.medicine_id AND b.expiry_date > CURRENT_DATE
    ORDER BY b.expiry_date ASC
    LIMIT 2
) t
WHERE m.criticality = 'LIFE_SAVING'
ORDER BY m.name, t.expiry_date
LIMIT 16;

\echo ''
\echo '=== C7: FILTER + HAVING — hospitals with high critical ratio ==='
SELECT h.name, h.city,
       COUNT(*) AS total_requests,
       COUNT(*) FILTER (WHERE r.priority = 'CRITICAL') AS critical,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.priority = 'CRITICAL')
             / COUNT(*), 1) AS critical_pct
FROM hospital h
JOIN emergency_request r ON r.hospital_id = h.hospital_id
GROUP BY h.hospital_id, h.name, h.city
HAVING COUNT(*) > 200
   AND COUNT(*) FILTER (WHERE r.priority = 'CRITICAL') * 10 > COUNT(*)
ORDER BY critical_pct DESC
LIMIT 10;

\echo ''
\echo '=== C8: Self-join — warehouses in the same city ==='
SELECT w1.name AS warehouse_a, w2.name AS warehouse_b, w1.city
FROM warehouse w1
JOIN warehouse w2 ON w1.city = w2.city AND w1.warehouse_id < w2.warehouse_id
ORDER BY w1.city
LIMIT 10;
