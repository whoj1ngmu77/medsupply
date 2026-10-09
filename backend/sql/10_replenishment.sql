-- =====================================================================
-- AUTOMATIC INVENTORY REPLENISHMENT (Auto Stock-Up)
-- =====================================================================
-- ADDITIVE ONLY. Creates new relations; alters nothing existing except
-- two nullable columns with defaults. Does not touch inventory_batch,
-- emergency_request, allocation, or the allocation transaction.
--
-- Direction of flow (note this is the INVERSE of emergency_request):
--     emergency_request : warehouse stock --> hospital   (demand side)
--     purchase_order    : supplier        --> warehouse  (supply side)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Supplier catalogue: which supplier can supply which medicine.
--    Required by the "identify the appropriate supplier" rule. If an
--    equivalent already exists we keep both; this one is authoritative
--    for replenishment only.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS supplier_medicine (
    supplier_id     INTEGER NOT NULL REFERENCES supplier(supplier_id)
                    ON DELETE CASCADE,
    medicine_id     INTEGER NOT NULL REFERENCES medicine(medicine_id)
                    ON DELETE CASCADE,
    unit_price      NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    lead_time_days  INTEGER NOT NULL DEFAULT 3 CHECK (lead_time_days >= 0),
    min_order_qty   INTEGER NOT NULL DEFAULT 100 CHECK (min_order_qty > 0),
    pack_size       INTEGER NOT NULL DEFAULT 50  CHECK (pack_size > 0),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (supplier_id, medicine_id)
);

-- ---------------------------------------------------------------------
-- 2. Stock policy: the reorder rule, per (warehouse, medicine).
--    Per-warehouse because stock is physically held per warehouse —
--    a global per-medicine threshold cannot say WHERE to deliver.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_policy (
    policy_id            SERIAL PRIMARY KEY,
    warehouse_id         INTEGER NOT NULL REFERENCES warehouse(warehouse_id)
                         ON DELETE CASCADE,
    medicine_id          INTEGER NOT NULL REFERENCES medicine(medicine_id)
                         ON DELETE RESTRICT,
    min_threshold        INTEGER NOT NULL CHECK (min_threshold >= 0),
    target_level         INTEGER NOT NULL CHECK (target_level > 0),
    preferred_supplier_id INTEGER REFERENCES supplier(supplier_id)
                         ON DELETE SET NULL,
    auto_order_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_stock_policy UNIQUE (warehouse_id, medicine_id),
    -- you cannot restock to a level below the point that triggers it
    CONSTRAINT chk_target_above_threshold CHECK (target_level > min_threshold)
);

-- ---------------------------------------------------------------------
-- 3. Purchase order header
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_order (
    po_id           SERIAL PRIMARY KEY,
    po_number       VARCHAR(32) NOT NULL UNIQUE,
    supplier_id     INTEGER NOT NULL REFERENCES supplier(supplier_id)
                    ON DELETE RESTRICT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouse(warehouse_id)
                    ON DELETE RESTRICT,
    po_status       VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (po_status IN ('PENDING','SENT','CONFIRMED',
                                         'SHIPPED','DELIVERED','CANCELLED')),
    total_value     NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_value >= 0),

    -- Honesty flag. TRUE means no real supplier was ever contacted.
    is_simulated    BOOLEAN NOT NULL DEFAULT TRUE,
    dispatch_channel VARCHAR(20) NOT NULL DEFAULT 'SIMULATED'
                    CHECK (dispatch_channel IN ('SIMULATED','EMAIL','API')),

    triggered_by    VARCHAR(20) NOT NULL DEFAULT 'AUTO'
                    CHECK (triggered_by IN ('AUTO','MANUAL')),
    raised_by       INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    confirmed_at    TIMESTAMPTZ,
    shipped_at      TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    expected_by     DATE
);

-- ---------------------------------------------------------------------
-- 4. Purchase order lines
--
--    warehouse_id is DENORMALIZED from the header onto the line. This is
--    deliberate and is the same trade-off as qty_reserved on
--    inventory_batch: the partial unique index below needs both
--    warehouse and medicine on one row, and a partial unique index
--    cannot span a join. Documented in docs/12_replenishment.md.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_order_line (
    po_line_id      SERIAL PRIMARY KEY,
    po_id           INTEGER NOT NULL REFERENCES purchase_order(po_id)
                    ON DELETE CASCADE,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouse(warehouse_id)
                    ON DELETE RESTRICT,
    medicine_id     INTEGER NOT NULL REFERENCES medicine(medicine_id)
                    ON DELETE RESTRICT,
    qty_ordered     INTEGER NOT NULL CHECK (qty_ordered > 0),
    qty_received    INTEGER NOT NULL DEFAULT 0 CHECK (qty_received >= 0),
    unit_price      NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    line_status     VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (line_status IN ('PENDING','SENT','CONFIRMED',
                                           'SHIPPED','DELIVERED','CANCELLED')),

    -- cannot receive more than was ordered
    CONSTRAINT chk_received_le_ordered CHECK (qty_received <= qty_ordered),
    CONSTRAINT uq_po_line UNIQUE (po_id, medicine_id)
);

-- =====================================================================
-- THE CORE INVARIANT OF THIS FEATURE
--
-- At most ONE open order line may exist per (warehouse, medicine).
-- This is requirement 6 (no duplicate orders) enforced by the DATABASE,
-- not by an application if-check. Two concurrent scans both checking
-- "is there an open order?" is a TOCTOU race: both see none, both
-- insert, both succeed. With this index the second INSERT fails.
--
-- Exactly the same reasoning as CHECK (qty_reserved <= qty_on_hand).
-- =====================================================================
CREATE UNIQUE INDEX IF NOT EXISTS uq_open_po_line
    ON purchase_order_line (warehouse_id, medicine_id)
    WHERE line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED');

-- ---------------------------------------------------------------------
-- 5. Replenishment log — every scan decision, ordered or not.
--    Requirement 7. This is an application audit log, NOT the WAL.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS replenishment_log (
    log_id          SERIAL PRIMARY KEY,
    scan_id         UUID NOT NULL,
    policy_id       INTEGER REFERENCES stock_policy(policy_id) ON DELETE SET NULL,
    warehouse_id    INTEGER,
    medicine_id     INTEGER,
    decision        VARCHAR(30) NOT NULL
                    CHECK (decision IN ('ORDERED','SKIPPED_ABOVE_THRESHOLD',
                                        'SKIPPED_ORDER_OPEN','SKIPPED_NO_SUPPLIER',
                                        'SKIPPED_DISABLED','FAILED')),
    qty_available   INTEGER,
    qty_on_order    INTEGER,
    min_threshold   INTEGER,
    target_level    INTEGER,
    qty_ordered     INTEGER,
    po_id           INTEGER REFERENCES purchase_order(po_id) ON DELETE SET NULL,
    note            TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 6. Notifications — requirement 7
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification (
    notification_id SERIAL PRIMARY KEY,
    recipient_role  VARCHAR(30) NOT NULL,
    recipient_user_id INTEGER REFERENCES user_account(user_id) ON DELETE CASCADE,
    category        VARCHAR(30) NOT NULL DEFAULT 'REPLENISHMENT',
    severity        VARCHAR(20) NOT NULL DEFAULT 'INFO'
                    CHECK (severity IN ('INFO','WARNING','CRITICAL')),
    title           VARCHAR(200) NOT NULL,
    body            TEXT,
    po_id           INTEGER REFERENCES purchase_order(po_id) ON DELETE CASCADE,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 7. Two additive columns on existing tables.
--    Both nullable / defaulted — no existing row or query breaks.
-- ---------------------------------------------------------------------
ALTER TABLE inventory_batch
    ADD COLUMN IF NOT EXISTS source_po_line_id INTEGER
    REFERENCES purchase_order_line(po_line_id) ON DELETE SET NULL;

ALTER TABLE warehouse
    ADD COLUMN IF NOT EXISTS auto_replenish_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- ---------------------------------------------------------------------
-- 8. Supporting indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_policy_wh_med
    ON stock_policy (warehouse_id, medicine_id) WHERE auto_order_enabled;
CREATE INDEX IF NOT EXISTS idx_po_status
    ON purchase_order (po_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_po_supplier
    ON purchase_order (supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_line_po
    ON purchase_order_line (po_id);
CREATE INDEX IF NOT EXISTS idx_replen_log_scan
    ON replenishment_log (scan_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_replen_log_recent
    ON replenishment_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_unread
    ON notification (recipient_role, created_at DESC) WHERE NOT is_read;
CREATE INDEX IF NOT EXISTS idx_batch_source_po
    ON inventory_batch (source_po_line_id) WHERE source_po_line_id IS NOT NULL;

ANALYZE stock_policy;
ANALYZE purchase_order;
ANALYZE purchase_order_line;

-- PO numbers get their own sequence; sharing purchase_order_po_id_seq
-- consumed two values per order (number + identity), leaving gaps.
CREATE SEQUENCE IF NOT EXISTS po_number_seq START 1;
