-- The six queries measured before and after indexing.
-- Each corresponds to a real filter exposed by a Phase 5/6 endpoint.

-- Q1: batch lookup by warehouse + medicine  (GET /inventory)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM inventory_batch WHERE warehouse_id = 5 AND medicine_id = 12;

-- Q2: expiry scan  (GET /inventory/expiring)
EXPLAIN (ANALYZE, BUFFERS)
SELECT batch_id, batch_number, expiry_date FROM inventory_batch
WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 90;

-- Q3: allocation queue  (GET /requests/queue)
EXPLAIN (ANALYZE, BUFFERS)
SELECT request_id, hospital_id, qty_requested FROM emergency_request
WHERE request_status IN ('PENDING','PARTIAL') AND priority = 'CRITICAL';

-- Q4: FEFO batch selection  (the Phase 6 allocation hot path)
EXPLAIN (ANALYZE, BUFFERS)
SELECT batch_id, qty_on_hand - qty_reserved AS avail FROM inventory_batch
WHERE medicine_id = 12 AND expiry_date > CURRENT_DATE
  AND (qty_on_hand - qty_reserved) > 0
ORDER BY expiry_date ASC, batch_id ASC;

-- Q5: hospital request history  (GET /requests?hospital_id=)
EXPLAIN (ANALYZE, BUFFERS)
SELECT request_id, medicine_id, qty_requested, request_status
FROM emergency_request WHERE hospital_id = 42
ORDER BY requested_at DESC LIMIT 50;

-- Q6: join-heavy shortage report  (GET /medicines/shortages)
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.name, SUM(b.qty_on_hand - b.qty_reserved) AS avail
FROM medicine m
JOIN inventory_batch b ON b.medicine_id = m.medicine_id
WHERE m.criticality = 'LIFE_SAVING' AND b.expiry_date > CURRENT_DATE
GROUP BY m.name;
