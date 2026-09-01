# Relational Schema — MedSupply

## Relations (3NF/BCNF)

HOSPITAL (hospital_id PK, name, reg_number UK, city,
bed_capacity, emergency_level)

MEDICINE_CATEGORY (category_id PK, category_name UK)

MANUFACTURER (manufacturer_id PK, manufacturer_name UK, country)

MEDICINE (medicine_id PK, name, category_id FK, manufacturer_id FK,
unit, criticality)

WAREHOUSE (warehouse_id PK, name, city, storage_capacity)

EMERGENCY_REQUEST (request_id PK, hospital_id FK, medicine_id FK,
qty_requested, priority, requested_at,
required_by, request_status)

INVENTORY_BATCH (batch_id PK, warehouse_id FK, medicine_id FK,
batch_number, qty_on_hand, qty_reserved, expiry_date,
UNIQUE(warehouse_id, batch_number))

ALLOCATION (allocation_id PK, request_id FK, batch_id FK,
qty_allocated, allocated_at, allocation_status,
UNIQUE(request_id, batch_id))

SUPPLIER (supplier_id PK, name, gst_number UK, contact_email, rating)

SUPPLY_CONSIGNMENT (consignment_id PK, supplier_id FK, medicine_id FK,
warehouse_id FK, batch_id FK, qty_supplied,
supplied_on, unit_price)

SHIPMENT (shipment_id PK, allocation_id FK UK, vehicle_number,
dispatched_at, expected_at, delivered_at, delivery_status)


Additional relations from BCNF/4NF analysis (see 04_normalization.md):

CUSTODIAN (custodian_id PK, warehouse_id FK, name)
CUSTODIAN_CATEGORY (custodian_id FK, category_id FK,
PK (custodian_id, category_id))
WAREHOUSE_CERTIFICATION (warehouse_id FK, certification,
PK (warehouse_id, certification))
WAREHOUSE_SERVICE_AREA (warehouse_id FK, district,
PK (warehouse_id, district))


## Candidate Keys

| Relation | Primary key | Other candidate keys |
|---|---|---|
| HOSPITAL | hospital_id | reg_number |
| WAREHOUSE | warehouse_id | — |
| MEDICINE_CATEGORY | category_id | category_name |
| MANUFACTURER | manufacturer_id | manufacturer_name |
| MEDICINE | medicine_id | — |
| INVENTORY_BATCH | batch_id | (warehouse_id, batch_number) |
| EMERGENCY_REQUEST | request_id | — |
| ALLOCATION | allocation_id | (request_id, batch_id) |
| SUPPLIER | supplier_id | gst_number |
| SUPPLY_CONSIGNMENT | consignment_id | batch_id |
| SHIPMENT | shipment_id | allocation_id |
| USER_ACCOUNT | user_id | username, email |

## Integrity Constraints

### Domain / CHECK
- `qty_requested > 0`, `qty_allocated > 0`
- `qty_on_hand >= 0`, `qty_reserved >= 0`
- **`qty_reserved <= qty_on_hand`** — the database-level backstop for the entire concurrency demo
- `expiry_date > mfg_date`
- `priority IN ('LOW','MEDIUM','HIGH','CRITICAL')`
- `request_status IN ('PENDING','PARTIAL','ALLOCATED','DISPATCHED','DELIVERED','REJECTED')`
- `criticality IN ('ROUTINE','ESSENTIAL','LIFE_SAVING')`

### Referential
- `ALLOCATION.request_id -> EMERGENCY_REQUEST` — ON DELETE RESTRICT
- `ALLOCATION.batch_id -> INVENTORY_BATCH` — ON DELETE RESTRICT
- `SHIPMENT.allocation_id -> ALLOCATION` — ON DELETE CASCADE
- `MEDICINE.category_id -> MEDICINE_CATEGORY` — ON DELETE RESTRICT

RESTRICT is chosen deliberately: cascading a delete through allocations would silently destroy the audit trail of who received scarce medicine.

### Semantic constraints not expressible in DDL
Enforced in the service layer (Phase 6):
- Sum of `qty_allocated` across a request's allocations <= `qty_requested`
- Sum of allocations against a batch <= that batch's `qty_reserved`
- A batch may not be allocated if `expiry_date < CURRENT_DATE`

## Cross-Database Boundary

`EMERGENCY_REQUEST.incident_id` references a MongoDB ObjectId. PostgreSQL cannot enforce this FK. Stored as nullable `VARCHAR(24)`, validated in the application layer.

This is the honest cost of polyglot persistence: referential integrity traded for schema flexibility.
