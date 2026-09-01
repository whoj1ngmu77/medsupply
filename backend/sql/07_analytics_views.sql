-- Analytics views. Demonstrate CTEs, window functions, FILTER,
-- and multi-level aggregation.

DROP VIEW IF EXISTS v_dashboard_kpis CASCADE;
DROP VIEW IF EXISTS v_requests_by_day CASCADE;
DROP VIEW IF EXISTS v_medicine_demand CASCADE;
DROP VIEW IF EXISTS v_hospital_activity CASCADE;
DROP VIEW IF EXISTS v_allocation_efficiency CASCADE;
DROP VIEW IF EXISTS v_stock_by_category CASCADE;

-- The eight headline metrics, computed in ONE pass using scalar
-- subqueries rather than eight separate round trips.
CREATE VIEW v_dashboard_kpis AS
SELECT
    (SELECT COUNT(*) FROM hospital) AS total_hospitals,
    (SELECT COUNT(*) FROM warehouse) AS total_warehouses,
    (SELECT COUNT(*) FROM medicine) AS total_medicines,
    (SELECT COALESCE(SUM(qty_on_hand - qty_reserved), 0)
       FROM inventory_batch WHERE expiry_date > CURRENT_DATE)
       AS units_available,
    (SELECT COUNT(*) FROM v_critical_shortage) AS critical_shortages,
    (SELECT COUNT(*) FROM emergency_request
      WHERE request_status = 'PENDING') AS pending_requests,
    (SELECT COUNT(*) FROM emergency_request
      WHERE request_status IN ('ALLOCATED','PARTIAL')) AS allocated_requests,
    (SELECT COUNT(*) FROM emergency_request
      WHERE request_status = 'DISPATCHED') AS in_transit_requests,
    (SELECT COUNT(DISTINCT b.medicine_id) FROM inventory_batch b
      WHERE b.expiry_date > CURRENT_DATE
      GROUP BY b.medicine_id
      HAVING SUM(b.qty_on_hand - b.qty_reserved) < 1000
      LIMIT 1) AS low_stock_flag,
    (SELECT COUNT(*) FROM inventory_batch
      WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 90)
      AS expiring_batches,
    (SELECT COUNT(*) FROM emergency_request
      WHERE priority = 'CRITICAL'
        AND request_status IN ('PENDING','PARTIAL')) AS critical_open;

-- Time series with a window function for the running total.
CREATE VIEW v_requests_by_day AS
SELECT
    DATE(requested_at) AS day,
    COUNT(*) AS requests,
    COUNT(*) FILTER (WHERE priority = 'CRITICAL') AS critical,
    COUNT(*) FILTER (WHERE request_status = 'PENDING') AS pending,
    COUNT(*) FILTER (WHERE request_status = 'DELIVERED') AS delivered,
    SUM(qty_requested) AS units_requested,
    SUM(SUM(qty_requested)) OVER (ORDER BY DATE(requested_at))
        AS cumulative_units
FROM emergency_request
WHERE requested_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(requested_at)
ORDER BY day;

-- Demand vs supply per medicine. CTEs keep it readable.
CREATE VIEW v_medicine_demand AS
WITH demand AS (
    SELECT medicine_id,
           COUNT(*) AS request_count,
           SUM(qty_requested) AS total_requested,
           SUM(qty_fulfilled) AS total_fulfilled
    FROM emergency_request
    GROUP BY medicine_id
),
supply AS (
    SELECT medicine_id,
           SUM(qty_on_hand - qty_reserved) AS available,
           COUNT(*) AS batch_count
    FROM inventory_batch
    WHERE expiry_date > CURRENT_DATE
    GROUP BY medicine_id
)
SELECT
    m.medicine_id, m.name AS medicine_name, m.criticality, m.unit,
    COALESCE(d.request_count, 0) AS request_count,
    COALESCE(d.total_requested, 0) AS total_requested,
    COALESCE(d.total_fulfilled, 0) AS total_fulfilled,
    COALESCE(s.available, 0) AS available,
    COALESCE(s.batch_count, 0) AS batch_count,
    CASE WHEN COALESCE(d.total_requested, 0) = 0 THEN NULL
         ELSE ROUND(100.0 * COALESCE(d.total_fulfilled, 0)
                    / d.total_requested, 1)
    END AS fulfilment_rate_pct,
    CASE WHEN COALESCE(s.available, 0) = 0 THEN 'OUT_OF_STOCK'
         WHEN COALESCE(s.available, 0) < 1000 THEN 'LOW'
         WHEN COALESCE(s.available, 0) < 5000 THEN 'MODERATE'
         ELSE 'HEALTHY' END AS stock_status
FROM medicine m
LEFT JOIN demand d ON d.medicine_id = m.medicine_id
LEFT JOIN supply s ON s.medicine_id = m.medicine_id;

-- RANK() over hospitals by request volume.
CREATE VIEW v_hospital_activity AS
SELECT
    h.hospital_id, h.name AS hospital_name, h.city, h.emergency_level,
    h.bed_capacity,
    COUNT(r.request_id) AS total_requests,
    COUNT(r.request_id) FILTER (
        WHERE r.request_status IN ('PENDING','PARTIAL')) AS open_requests,
    COALESCE(SUM(r.qty_requested), 0) AS units_requested,
    COALESCE(SUM(r.qty_fulfilled), 0) AS units_received,
    RANK() OVER (ORDER BY COUNT(r.request_id) DESC) AS activity_rank
FROM hospital h
LEFT JOIN emergency_request r ON r.hospital_id = h.hospital_id
GROUP BY h.hospital_id, h.name, h.city, h.emergency_level, h.bed_capacity;

-- Allocation efficiency: how many batches a request needed.
CREATE VIEW v_allocation_efficiency AS
SELECT
    r.request_id, r.priority, r.request_status,
    r.qty_requested, r.qty_fulfilled,
    COUNT(a.allocation_id) AS batches_used,
    ROUND(AVG(a.qty_allocated), 0) AS avg_qty_per_batch,
    MIN(a.allocated_at) AS first_allocation,
    MAX(a.allocated_at) AS last_allocation,
    EXTRACT(EPOCH FROM (MIN(a.allocated_at) - r.requested_at))/3600
        AS hours_to_first_allocation
FROM emergency_request r
JOIN allocation a ON a.request_id = r.request_id
                 AND a.allocation_status <> 'CANCELLED'
GROUP BY r.request_id, r.priority, r.request_status,
         r.qty_requested, r.qty_fulfilled, r.requested_at;

CREATE VIEW v_stock_by_category AS
SELECT
    c.category_id, c.name AS category_name,
    COUNT(DISTINCT m.medicine_id) AS medicine_count,
    COUNT(b.batch_id) AS batch_count,
    COALESCE(SUM(b.qty_on_hand), 0) AS units_on_hand,
    COALESCE(SUM(b.qty_reserved), 0) AS units_reserved,
    COALESCE(SUM(b.qty_on_hand - b.qty_reserved), 0) AS units_available,
    COUNT(b.batch_id) FILTER (
        WHERE b.expiry_date <= CURRENT_DATE + 90) AS expiring_soon
FROM medicine_category c
LEFT JOIN medicine m ON m.category_id = c.category_id
LEFT JOIN inventory_batch b ON b.medicine_id = m.medicine_id
                           AND b.expiry_date > CURRENT_DATE
GROUP BY c.category_id, c.name
ORDER BY units_available DESC;
