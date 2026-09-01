-- Analytical views. Used by the dashboard (Phase 11) and relational algebra doc.

DROP VIEW IF EXISTS v_available_inventory CASCADE;
DROP VIEW IF EXISTS v_critical_shortage CASCADE;
DROP VIEW IF EXISTS v_expiring_soon CASCADE;
DROP VIEW IF EXISTS v_request_fulfilment CASCADE;
DROP VIEW IF EXISTS v_warehouse_utilisation CASCADE;

-- Derived attribute: available = on_hand - reserved.
-- Kept as a view, NOT a stored column, to avoid a third value to keep consistent.
CREATE VIEW v_available_inventory AS
SELECT
    b.batch_id,
    b.warehouse_id,
    w.name AS warehouse_name,
    b.medicine_id,
    m.name AS medicine_name,
    m.criticality,
    b.batch_number,
    b.qty_on_hand,
    b.qty_reserved,
    (b.qty_on_hand - b.qty_reserved) AS qty_available,
    b.expiry_date
FROM inventory_batch b
JOIN warehouse w ON w.warehouse_id = b.warehouse_id
JOIN medicine  m ON m.medicine_id  = b.medicine_id
WHERE b.expiry_date > CURRENT_DATE;

CREATE VIEW v_critical_shortage AS
SELECT
    m.medicine_id,
    m.name AS medicine_name,
    m.criticality,
    COALESCE(SUM(b.qty_on_hand - b.qty_reserved), 0) AS total_available,
    COUNT(DISTINCT r.request_id) FILTER (
        WHERE r.request_status IN ('PENDING','PARTIAL')
    ) AS open_requests
FROM medicine m
LEFT JOIN inventory_batch b
       ON b.medicine_id = m.medicine_id AND b.expiry_date > CURRENT_DATE
LEFT JOIN emergency_request r
       ON r.medicine_id = m.medicine_id
WHERE m.criticality IN ('ESSENTIAL','LIFE_SAVING')
GROUP BY m.medicine_id, m.name, m.criticality
HAVING COALESCE(SUM(b.qty_on_hand - b.qty_reserved), 0) < 500;

CREATE VIEW v_expiring_soon AS
SELECT
    b.batch_id,
    b.batch_number,
    m.name AS medicine_name,
    w.name AS warehouse_name,
    b.qty_on_hand - b.qty_reserved AS qty_available,
    b.expiry_date,
    (b.expiry_date - CURRENT_DATE) AS days_to_expiry
FROM inventory_batch b
JOIN medicine  m ON m.medicine_id  = b.medicine_id
JOIN warehouse w ON w.warehouse_id = b.warehouse_id
WHERE b.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
  AND b.qty_on_hand > b.qty_reserved;

CREATE VIEW v_request_fulfilment AS
SELECT
    r.request_id,
    h.name AS hospital_name,
    m.name AS medicine_name,
    r.qty_requested,
    COALESCE(SUM(a.qty_allocated), 0) AS qty_allocated,
    r.qty_requested - COALESCE(SUM(a.qty_allocated), 0) AS qty_outstanding,
    r.priority,
    r.request_status,
    r.requested_at,
    r.required_by
FROM emergency_request r
JOIN hospital h ON h.hospital_id = r.hospital_id
JOIN medicine m ON m.medicine_id = r.medicine_id
LEFT JOIN allocation a
       ON a.request_id = r.request_id
      AND a.allocation_status <> 'CANCELLED'
GROUP BY r.request_id, h.name, m.name, r.qty_requested,
         r.priority, r.request_status, r.requested_at, r.required_by;

CREATE VIEW v_warehouse_utilisation AS
SELECT
    w.warehouse_id,
    w.name AS warehouse_name,
    w.city,
    w.storage_capacity,
    COALESCE(SUM(b.qty_on_hand), 0) AS units_stored,
    ROUND(
        100.0 * COALESCE(SUM(b.qty_on_hand), 0) / NULLIF(w.storage_capacity, 0),
        2
    ) AS utilisation_pct,
    COUNT(b.batch_id) AS batch_count
FROM warehouse w
LEFT JOIN inventory_batch b ON b.warehouse_id = w.warehouse_id
GROUP BY w.warehouse_id, w.name, w.city, w.storage_capacity;
