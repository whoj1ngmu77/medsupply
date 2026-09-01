-- Indexes derived from actual query predicates, not guesswork.
-- Each is justified in docs/05_indexing_report.md.

-- Q1: composite. Column order matters — equality columns first, and
-- the more selective one leads. 60k batches / 40 warehouses = 1500 rows
-- per warehouse; / 20 medicines = 3000 per medicine. warehouse_id is
-- the more selective, so it leads.
CREATE INDEX IF NOT EXISTS idx_batch_wh_med
    ON inventory_batch (warehouse_id, medicine_id);

-- Q2: range scan on a date. B-tree handles ranges natively;
-- a hash index could NOT serve this query at all.
CREATE INDEX IF NOT EXISTS idx_batch_expiry
    ON inventory_batch (expiry_date);

-- Q4: the allocation hot path. Leading equality (medicine_id), then the
-- ORDER BY columns in matching order, so the index also supplies the
-- sort and the planner can skip an explicit Sort node.
CREATE INDEX IF NOT EXISTS idx_batch_fefo
    ON inventory_batch (medicine_id, expiry_date, batch_id);

-- Q3: PARTIAL index. Only ~35% of requests are PENDING/PARTIAL, so the
-- index covers a third of the table and stays hot in cache. This is the
-- most interesting index in the project.
CREATE INDEX IF NOT EXISTS idx_request_open
    ON emergency_request (priority, required_by)
    WHERE request_status IN ('PENDING', 'PARTIAL');

-- Q5: equality + sort direction matching the query's ORDER BY DESC.
CREATE INDEX IF NOT EXISTS idx_request_hospital
    ON emergency_request (hospital_id, requested_at DESC);

-- Q6 support
CREATE INDEX IF NOT EXISTS idx_medicine_criticality
    ON medicine (criticality);

-- FK indexes. PostgreSQL does NOT auto-index foreign keys (unlike MySQL);
-- without these, every parent DELETE scans the child table.
CREATE INDEX IF NOT EXISTS idx_allocation_request ON allocation (request_id);
CREATE INDEX IF NOT EXISTS idx_allocation_batch   ON allocation (batch_id);
CREATE INDEX IF NOT EXISTS idx_event_request      ON allocation_event (request_id);

-- Hash index: equality only, no ranges, no sorting. Included to
-- demonstrate the B-tree/hash distinction with a real object.
CREATE INDEX IF NOT EXISTS idx_hospital_reg_hash
    ON hospital USING HASH (reg_number);

ANALYZE inventory_batch;
ANALYZE emergency_request;
ANALYZE medicine;
ANALYZE allocation;
