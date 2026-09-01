-- MedSupply — Core Schema (BCSE302L)
-- All relations in 3NF/BCNF. See docs/04_normalization.md for derivation.

DROP TABLE IF EXISTS allocation_event CASCADE;
DROP TABLE IF EXISTS shipment CASCADE;
DROP TABLE IF EXISTS allocation CASCADE;
DROP TABLE IF EXISTS emergency_request CASCADE;
DROP TABLE IF EXISTS supply_consignment CASCADE;
DROP TABLE IF EXISTS inventory_batch CASCADE;
DROP TABLE IF EXISTS custodian_category CASCADE;
DROP TABLE IF EXISTS custodian CASCADE;
DROP TABLE IF EXISTS warehouse_certification CASCADE;
DROP TABLE IF EXISTS warehouse_service_area CASCADE;
DROP TABLE IF EXISTS user_account CASCADE;
DROP TABLE IF EXISTS medicine CASCADE;
DROP TABLE IF EXISTS medicine_category CASCADE;
DROP TABLE IF EXISTS manufacturer CASCADE;
DROP TABLE IF EXISTS supplier CASCADE;
DROP TABLE IF EXISTS warehouse CASCADE;
DROP TABLE IF EXISTS hospital CASCADE;

-- ---------- Reference entities ----------

CREATE TABLE hospital (
    hospital_id      SERIAL PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    reg_number       VARCHAR(50)  NOT NULL UNIQUE,
    address          VARCHAR(255),
    city             VARCHAR(100) NOT NULL,
    state            VARCHAR(100),
    latitude         NUMERIC(9,6),
    longitude        NUMERIC(9,6),
    bed_capacity     INTEGER      NOT NULL CHECK (bed_capacity > 0),
    emergency_level  VARCHAR(20)  NOT NULL DEFAULT 'NORMAL'
                     CHECK (emergency_level IN ('NORMAL','ELEVATED','HIGH','CRITICAL')),
    contact_phone    VARCHAR(20),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE warehouse (
    warehouse_id     SERIAL PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    address          VARCHAR(255),
    city             VARCHAR(100) NOT NULL,
    latitude         NUMERIC(9,6),
    longitude        NUMERIC(9,6),
    storage_capacity INTEGER      NOT NULL CHECK (storage_capacity > 0),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE manufacturer (
    manufacturer_id  SERIAL PRIMARY KEY,
    name             VARCHAR(150) NOT NULL UNIQUE,
    country          VARCHAR(100),
    license_no       VARCHAR(60)
);

CREATE TABLE medicine_category (
    category_id      SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL UNIQUE,
    description      TEXT
);

CREATE TABLE medicine (
    medicine_id      SERIAL PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    generic_name     VARCHAR(150),
    category_id      INTEGER NOT NULL
                     REFERENCES medicine_category(category_id) ON DELETE RESTRICT,
    manufacturer_id  INTEGER NOT NULL
                     REFERENCES manufacturer(manufacturer_id) ON DELETE RESTRICT,
    unit             VARCHAR(30) NOT NULL,
    criticality      VARCHAR(20) NOT NULL DEFAULT 'ROUTINE'
                     CHECK (criticality IN ('ROUTINE','ESSENTIAL','LIFE_SAVING')),
    is_controlled    BOOLEAN NOT NULL DEFAULT FALSE,
    storage_temp     VARCHAR(30)
);

CREATE TABLE supplier (
    supplier_id      SERIAL PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    gst_number       VARCHAR(20) NOT NULL UNIQUE,
    contact_email    VARCHAR(150),
    contact_phone    VARCHAR(20),
    rating           NUMERIC(2,1) CHECK (rating BETWEEN 0 AND 5)
);

-- ---------- Users (EER specialization, single-table mapping) ----------

CREATE TABLE user_account (
    user_id          SERIAL PRIMARY KEY,
    username         VARCHAR(60)  NOT NULL UNIQUE,
    email            VARCHAR(150) NOT NULL UNIQUE,
    password_hash    VARCHAR(255) NOT NULL,
    full_name        VARCHAR(150),
    role             VARCHAR(30)  NOT NULL
                     CHECK (role IN ('ADMIN','HOSPITAL_STAFF','WAREHOUSE_STAFF',
                                     'SUPPLIER','EMERGENCY_COORDINATOR')),
    hospital_id      INTEGER REFERENCES hospital(hospital_id)   ON DELETE RESTRICT,
    warehouse_id     INTEGER REFERENCES warehouse(warehouse_id) ON DELETE RESTRICT,
    supplier_id      INTEGER REFERENCES supplier(supplier_id)   ON DELETE RESTRICT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Disjointness: exactly one org FK set, and it must match the role
    CONSTRAINT chk_role_org CHECK (
        (role = 'HOSPITAL_STAFF'  AND hospital_id IS NOT NULL
             AND warehouse_id IS NULL AND supplier_id IS NULL) OR
        (role = 'WAREHOUSE_STAFF' AND warehouse_id IS NOT NULL
             AND hospital_id IS NULL AND supplier_id IS NULL) OR
        (role = 'SUPPLIER'        AND supplier_id IS NOT NULL
             AND hospital_id IS NULL AND warehouse_id IS NULL) OR
        (role IN ('ADMIN','EMERGENCY_COORDINATOR')
             AND hospital_id IS NULL AND warehouse_id IS NULL AND supplier_id IS NULL)
    )
);

-- ---------- 4NF decomposition of warehouse multivalued attributes ----------

CREATE TABLE warehouse_certification (
    warehouse_id     INTEGER NOT NULL
                     REFERENCES warehouse(warehouse_id) ON DELETE CASCADE,
    certification    VARCHAR(60) NOT NULL,
    PRIMARY KEY (warehouse_id, certification)
);

CREATE TABLE warehouse_service_area (
    warehouse_id     INTEGER NOT NULL
                     REFERENCES warehouse(warehouse_id) ON DELETE CASCADE,
    district         VARCHAR(100) NOT NULL,
    PRIMARY KEY (warehouse_id, district)
);

-- ---------- BCNF decomposition of stock custodian ----------

CREATE TABLE custodian (
    custodian_id     SERIAL PRIMARY KEY,
    warehouse_id     INTEGER NOT NULL
                     REFERENCES warehouse(warehouse_id) ON DELETE RESTRICT,
    name             VARCHAR(150) NOT NULL
);

CREATE TABLE custodian_category (
    custodian_id     INTEGER NOT NULL
                     REFERENCES custodian(custodian_id) ON DELETE CASCADE,
    category_id      INTEGER NOT NULL
                     REFERENCES medicine_category(category_id) ON DELETE RESTRICT,
    PRIMARY KEY (custodian_id, category_id)
);

-- ---------- Inventory (weak entity, surrogate PK + natural UNIQUE) ----------

CREATE TABLE inventory_batch (
    batch_id         SERIAL PRIMARY KEY,
    warehouse_id     INTEGER NOT NULL
                     REFERENCES warehouse(warehouse_id) ON DELETE RESTRICT,
    medicine_id      INTEGER NOT NULL
                     REFERENCES medicine(medicine_id) ON DELETE RESTRICT,
    batch_number     VARCHAR(60) NOT NULL,
    qty_on_hand      INTEGER NOT NULL CHECK (qty_on_hand >= 0),
    qty_reserved     INTEGER NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0),
    mfg_date         DATE,
    expiry_date      DATE NOT NULL,
    unit_cost        NUMERIC(10,2) CHECK (unit_cost >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- FD8: (warehouse_id, batch_number) -> batch_id
    CONSTRAINT uq_batch_natural UNIQUE (warehouse_id, batch_number),
    -- The single most important constraint in the project
    CONSTRAINT chk_reserved_le_onhand CHECK (qty_reserved <= qty_on_hand),
    CONSTRAINT chk_expiry_after_mfg CHECK (mfg_date IS NULL OR expiry_date > mfg_date)
);

-- ---------- Requests, allocation, dispatch ----------

CREATE TABLE emergency_request (
    request_id       SERIAL PRIMARY KEY,
    hospital_id      INTEGER NOT NULL
                     REFERENCES hospital(hospital_id) ON DELETE RESTRICT,
    medicine_id      INTEGER NOT NULL
                     REFERENCES medicine(medicine_id) ON DELETE RESTRICT,
    qty_requested    INTEGER NOT NULL CHECK (qty_requested > 0),
    qty_fulfilled    INTEGER NOT NULL DEFAULT 0 CHECK (qty_fulfilled >= 0),
    priority         VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'
                     CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    request_status   VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                     CHECK (request_status IN ('PENDING','PARTIAL','ALLOCATED',
                                               'DISPATCHED','DELIVERED','REJECTED')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    required_by      TIMESTAMPTZ,
    raised_by        INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    -- Cross-database soft reference to MongoDB. NOT enforceable as an FK.
    incident_id      VARCHAR(24),

    CONSTRAINT chk_fulfilled_le_requested CHECK (qty_fulfilled <= qty_requested)
);

CREATE TABLE allocation (
    allocation_id    SERIAL PRIMARY KEY,
    request_id       INTEGER NOT NULL
                     REFERENCES emergency_request(request_id) ON DELETE RESTRICT,
    batch_id         INTEGER NOT NULL
                     REFERENCES inventory_batch(batch_id) ON DELETE RESTRICT,
    qty_allocated    INTEGER NOT NULL CHECK (qty_allocated > 0),
    allocated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    allocated_by     INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    allocation_status VARCHAR(20) NOT NULL DEFAULT 'RESERVED'
                     CHECK (allocation_status IN ('RESERVED','DISPATCHED',
                                                  'DELIVERED','CANCELLED')),

    CONSTRAINT uq_allocation_natural UNIQUE (request_id, batch_id)
);

CREATE TABLE shipment (
    shipment_id      SERIAL PRIMARY KEY,
    allocation_id    INTEGER NOT NULL UNIQUE
                     REFERENCES allocation(allocation_id) ON DELETE CASCADE,
    vehicle_number   VARCHAR(30),
    driver_name      VARCHAR(150),
    dispatched_at    TIMESTAMPTZ,
    expected_at      TIMESTAMPTZ,
    delivered_at     TIMESTAMPTZ,
    delivery_status  VARCHAR(20) NOT NULL DEFAULT 'PREPARING'
                     CHECK (delivery_status IN ('PREPARING','IN_TRANSIT',
                                                'DELIVERED','FAILED'))
);

CREATE TABLE supply_consignment (
    consignment_id   SERIAL PRIMARY KEY,
    supplier_id      INTEGER NOT NULL
                     REFERENCES supplier(supplier_id) ON DELETE RESTRICT,
    medicine_id      INTEGER NOT NULL
                     REFERENCES medicine(medicine_id) ON DELETE RESTRICT,
    warehouse_id     INTEGER NOT NULL
                     REFERENCES warehouse(warehouse_id) ON DELETE RESTRICT,
    batch_id         INTEGER UNIQUE
                     REFERENCES inventory_batch(batch_id) ON DELETE RESTRICT,
    qty_supplied     INTEGER NOT NULL CHECK (qty_supplied > 0),
    supplied_on      DATE NOT NULL DEFAULT CURRENT_DATE,
    unit_price       NUMERIC(10,2) CHECK (unit_price >= 0)
);

-- ---------- Audit log (supports the recovery narrative) ----------

CREATE TABLE allocation_event (
    event_id         BIGSERIAL PRIMARY KEY,
    request_id       INTEGER,
    batch_id         INTEGER,
    event_type       VARCHAR(40) NOT NULL,
    old_value        TEXT,
    new_value        TEXT,
    txn_note         TEXT,
    actor_user_id    INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    actor_type       VARCHAR(20) NOT NULL DEFAULT 'USER'
                     CHECK (actor_type IN ('USER','SYSTEM')),
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
