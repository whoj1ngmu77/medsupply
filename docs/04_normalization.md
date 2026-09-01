# Normalization Analysis — MedSupply

Starting relation and FDs: see 03_functional_dependencies.md

## 1NF

**Rule:** all attributes atomic, no repeating groups.

Flatten the batch repeating group. The supplier group separates into its own relation (restocking is an independent fact from allocation).

R1NF (request_id, batch_id, hospital_id, hospital_name, hospital_city,
hospital_bed_capacity, hospital_emergency_level, medicine_id,
medicine_name, category_id, category_name, manufacturer_id,
manufacturer_name, manufacturer_country, unit, criticality,
qty_requested, priority, requested_at, required_by, request_status,
batch_number, warehouse_id, warehouse_name, warehouse_city,
warehouse_capacity, qty_on_hand, expiry_date,
qty_allocated, allocated_at, allocation_status)


**Candidate key:** `(request_id, batch_id)` — from FD9. Closure computation in 03_functional_dependencies.md.

**Anomalies present:**
- *Insertion:* cannot record a new warehouse until some allocation draws from it
- *Deletion:* deleting the last allocation for a hospital erases the hospital's details
- *Update:* renaming a hospital requires touching every allocation row it appears in

## 2NF

**Rule:** 1NF + no partial dependency of a non-prime attribute on part of a candidate key.

Key is `(request_id, batch_id)`. Violations:

- **FD1** — `request_id -> qty_requested, priority, ...` depends on part of the key
- **FD6** — `batch_id -> qty_on_hand, expiry_date, ...` depends on the other part
- **FD2, FD3** ride along transitively with FD1

Decompose:

REQUEST_2NF (request_id PK, hospital_id, hospital_name, hospital_city,
hospital_bed_capacity, hospital_emergency_level,
medicine_id, medicine_name, category_id, category_name,
manufacturer_id, manufacturer_name, manufacturer_country,
unit, criticality, qty_requested, priority,
requested_at, required_by, request_status)

BATCH_2NF (batch_id PK, batch_number, warehouse_id, warehouse_name,
warehouse_city, warehouse_capacity, medicine_id,
qty_on_hand, qty_reserved, expiry_date)

ALLOCATION_2NF (request_id, batch_id, qty_allocated,
allocated_at, allocation_status)
PK (request_id, batch_id)


ALLOCATION_2NF is already in BCNF — its only determinant is the full key.

## 3NF

**Rule:** 2NF + no transitive dependency of a non-prime attribute on a candidate key.

**In REQUEST_2NF:**
- `request_id -> hospital_id -> hospital_name` (FD1 then FD2)
- `request_id -> medicine_id -> medicine_name, category_id` (FD1 then FD3)
- `medicine_id -> category_id -> category_name` (FD3 then FD4)
- `medicine_id -> manufacturer_id -> manufacturer_name` (FD3 then FD5)

**In BATCH_2NF:**
- `batch_id -> warehouse_id -> warehouse_name, warehouse_city` (FD6 then FD7)

Decomposition yields the ten relations in 02_relational_schema.md.

The decomposition is **lossless** (every split was on a determinant that becomes the PK of one fragment and an FK in the other) and **dependency-preserving** (every FD1-FD11 is enforced within a single relation).

## BCNF

**Rule:** for every non-trivial FD `X -> Y`, `X` must be a superkey.

Checking each of the ten 3NF relations: every determinant is the primary key. **All ten are already in BCNF.**

### A genuine BCNF violation elsewhere in the design

Warehouses assign a custodian per medicine category; each custodian works at exactly one warehouse:

STOCK_CUSTODIAN (warehouse_id, category_id, custodian_id)

FD-A (warehouse_id, category_id) -> custodian_id
FD-B custodian_id -> warehouse_id


Candidate keys: `(warehouse_id, category_id)` and `(custodian_id, category_id)`.

`custodian_id` is a determinant (FD-B) but **not** a superkey — a custodian can cover several categories. The relation is in 3NF (`warehouse_id` is prime, so no 3NF violation) but **violates BCNF**.

Decompose:

CUSTODIAN (custodian_id PK, warehouse_id FK, name)
CUSTODIAN_CATEGORY (custodian_id FK, category_id FK,
PK (custodian_id, category_id))


**Trade-off, stated honestly:** this decomposition is lossless but **not dependency-preserving**. FD-A can no longer be checked within a single relation and needs a trigger or application-level check. This is the classic 3NF-vs-BCNF trade-off.

## 4NF

**Rule:** BCNF + no non-trivial multivalued dependency unless the determinant is a superkey.

A warehouse holds several certifications (cold-chain, controlled-substance, biohazard) and serves several districts. These facts are independent.

WAREHOUSE_ATTRIBUTES (warehouse_id, certification, district)

MVD-1 warehouse_id ->> certification
MVD-2 warehouse_id ->> district


A warehouse with 3 certifications and 4 districts forces **12 rows** to express 7 facts. Adding a certification means inserting 4 rows. No FD catches this redundancy.

Decompose:

WAREHOUSE_CERTIFICATION (warehouse_id FK, certification,
PK (warehouse_id, certification))
WAREHOUSE_SERVICE_AREA (warehouse_id FK, district,
PK (warehouse_id, district))


Rows drop from 12 to 7, and insertion is independent.

### Why SUPPLY_CONSIGNMENT is NOT a 4NF violation

It might look like an MVD candidate (supplier ->> medicine, supplier ->> warehouse), but it isn't. The three are *jointly* dependent: a consignment is one real event tying a specific supplier, medicine, and warehouse together with a quantity and date.

## Viva Preparation

1. Why is `(request_id, batch_id)` the candidate key of the 1NF relation? (Compute the closure.)
2. Show a partial dependency and explain why it breaks 2NF.
3. Your 3NF relations are already in BCNF — so why does BCNF exist as a separate normal form? (The STOCK_CUSTODIAN case.)
4. Is your BCNF decomposition dependency-preserving? (No — explain which FD is lost and how you enforce it.)
5. Why is SUPPLY_CONSIGNMENT not a 4NF violation?
6. Why keep `qty_reserved` as a stored column instead of deriving it from ALLOCATION? (Deliberate denormalization: it is the row taken FOR UPDATE in the allocation transaction. Deriving it would require an aggregate over a growing table on every allocation.)
