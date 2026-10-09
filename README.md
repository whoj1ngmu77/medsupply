# MedSupply — Emergency Medical Supply Management System

**BCSE302L · Database Systems · VIT Chennai**

A centralised system for allocating scarce medical supplies to hospitals
during emergencies, and for keeping warehouse stock replenished
automatically. The application exists to make database problems visible:
concurrency, consistency, indexing and query cost.

## Live

| | |
|---|---|
| Application | https://medsupply-kappa.vercel.app |
| API | https://medsupply-api-pdvy.onrender.com |
| API docs | https://medsupply-api-pdvy.onrender.com/docs |

Sign in with `admin` / `admin@12345`.

> The API runs on a free tier that sleeps after 15 minutes idle. The first
> request after a period of inactivity takes up to 50 seconds to wake.
> The hosted database is seeded small (8 hospitals, 60 batches) to stay
> within free-tier limits; run locally for the full dataset of 200
> hospitals and 60,000 batches.

## Team

| Name | Registration |
|---|---|
| Mukesh | 24BEL1014 |
| Deepakshi | 24BEL1022 |
| Shaheed | 24BEL1029 |
| Gayathri Menon | 24BEL1051 |
| Sahana | 24BEL1052 |

## The problem

A warehouse holds 100 units of a medicine. Two hospitals request it at the
same moment — one wants 70, the other 50. Both requests read the stock
level before either writes. Without a lock, both see 100, both proceed,
and 120 units are promised against 100 that exist.

This is the lost update problem, and it is the centre of the project. The
allocation engine prevents it by taking a row lock at **read** time:

```sql
SELECT ... FROM inventory_batch
WHERE medicine_id = :m AND qty_on_hand > qty_reserved
ORDER BY expiry_date ASC, batch_id ASC
FOR UPDATE;
```

Two things are happening:

- `FOR UPDATE` makes the second transaction wait and re-read, so it decides
  against the committed value rather than a stale one.
- `ORDER BY expiry_date, batch_id` makes every transaction acquire locks in
  the same sequence, which breaks the circular-wait condition and so
  prevents deadlock. It also implements FEFO — first expiring, first out.

Underneath both sits a database constraint that cannot be bypassed by any
code path: `CHECK (qty_reserved <= qty_on_hand)`.

## Architecture

Suppliers ──purchase orders──> Warehouses ──allocations──> Hospitals
^ ^ │
└── auto stock-up ──────────────┘<──── emergency request ───┘


Two loops in opposite directions. Demand pulls stock out toward hospitals;
supply pushes it back in from suppliers. Both touch the same inventory
rows, which is why the locking has to be correct.

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind, Recharts |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Relational | PostgreSQL 16 — 17 relations, transactional core |
| Document | MongoDB 7 — variable-shape incident records |
| Deployment | Vercel (web), Render (API), Neon (Postgres), Atlas (Mongo) |

**Why two databases.** Allocation is a consistency problem: a stale read
means a hospital is promised stock another hospital already received.
PostgreSQL gives transactions, row locks and foreign keys. Emergency
incidents are a different shape entirely — a flood record and a chemical
spill record share no fields at all. Six incident types, no common detail
schema; `GET /incidents/schema-variation` proves it. Forcing that into a
relational table would mean a wide mostly-NULL table, an EAV table that
loses typing, or one table per type.

## Automatic replenishment (Auto Stock-Up)

The supply-side counterpart to allocation. When warehouse stock for a
medicine falls to or below its configured threshold, the system raises a
purchase order against a supplier, tracks it through its lifecycle, and
receives the delivered stock back into inventory.

It runs on a background scheduler — no user action triggers it.

**Duplicate prevention is enforced by the database, not the application:**

```sql
CREATE UNIQUE INDEX uq_open_po_line
    ON purchase_order_line (warehouse_id, medicine_id)
    WHERE line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED');
```

A partial unique index permitting at most one open order per
(warehouse, medicine). An application-level "is an order already open?"
check would be a time-of-check/time-of-use race: two concurrent scans both
check, both see nothing, both insert. With this index, the second insert
fails. Same reasoning as the `CHECK` constraint on allocation.

Order quantity is computed, not fixed:
`target_level − available − already_on_order`, rounded up to the supplier's
pack size and floored at their minimum order quantity. Including the
on-order term is what makes repeated scans idempotent.

**All orders are simulated.** No supplier is contacted — no email, no API
call. Every order carries `is_simulated = TRUE` and
`dispatch_channel = 'SIMULATED'`, and the UI labels them as such.

## Measured results

Reproduce with `psql -f backend/sql/04_benchmark_queries.sql`; raw
`EXPLAIN ANALYZE` output is in `docs/measurements/`.

| Query | Before | After | Gain |
|---|---|---|---|
| Batch lookup by warehouse + medicine | 5.64 ms | 0.33 ms | 17× |
| Hospital request history | 2.03 ms | 0.05 ms | 38× |
| `v_critical_shortage` | 10,967 ms | 11.5 ms | **954×** |
| `/analytics/overview` | ~65 s | 137 ms | 474× |

The 954× came from rewriting the query, not from adding an index. Joining
`medicine` to both `inventory_batch` and `emergency_request` in one query
produced a fan-out cartesian product of 127 million rows. Aggregating each
child table separately in a CTE before joining reduced it to about 21 rows
per side. Query rewriting and index selection are separate tools, and
rewriting is the more powerful one when the plan shape itself is wrong.

## DBMS concepts demonstrated

| Concept | Where |
|---|---|
| ER / EER modelling | `docs/01_er_diagram.md` — weak and associative entities |
| Normalization UNF→BCNF | `docs/04_normalization.md` — includes a BCNF violation that is lossless but not dependency-preserving |
| Functional dependencies | `docs/03_functional_dependencies.md` |
| Indexing | 11 indexes: composite, partial, hash, range — `docs/05_indexing_report.md` |
| B+ tree, hashing | Interactive visualisers on the DBMS Demos page |
| Relational algebra | `docs/10_relational_algebra.md` |
| Query optimization | `docs/measurements/` — before/after `EXPLAIN ANALYZE` |
| ACID transactions | `app/services/allocation_service.py` |
| Concurrency control, 2PL | `docs/measurements/05_concurrency_labs.txt` — lost update reproduced then prevented |
| Deadlock | Induced, detected by PostgreSQL (SQLSTATE 40P01), prevented by lock ordering |
| Recovery | Rollback, savepoints, WAL, durability settings |
| NoSQL, CAP | `docs/09_nosql_cap.md` |

## Running locally

Requires Docker, or PostgreSQL 16 and MongoDB 7 installed directly.

```bash
docker compose up -d                    # databases

cd backend
pip install -r requirements.txt
psql "$PGPASS" -f sql/01_schema.sql     # or: python scripts/bootstrap_db.py
python scripts/seed_data.py --mode bulk # 200 hospitals, 60,000 batches
python scripts/set_passwords.py
python scripts/seed_incidents.py
python scripts/seed_replenishment.py
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install && npm run dev              # http://localhost:5173
```

### Credentials

| User | Password | Role |
|---|---|---|
| admin | admin@12345 | Administrator |
| coordinator | coord@12345 | Emergency coordinator |
| hosp1 | hosp1@12345 | Hospital staff |
| wh1 | wh1@12345 | Warehouse staff |

### Tests

```bash
cd backend && python -m pytest -v
```

20 tests. The one that matters is `test_never_over_allocates` — the
executable form of the core requirement.

### Demonstrating Auto Stock-Up

```bash
python scripts/demo_reset.py
```

Reduces selected warehouse stock below threshold. Open the Auto Stock-Up
page and watch the scheduler raise orders and walk them through the
pipeline without any user action.

## Repository layout

backend/
app/
services/allocation_service.py ACID allocation, FEFO, row locking
services/replenishment_service.py automatic purchase order generation
services/supplier_gateway.py simulated order lifecycle
services/scheduler.py background scan loops
dbms/ concurrency, deadlock, recovery labs
routers/ REST endpoints
sql/ schema, views, indexes, benchmarks
scripts/ seeding and demonstration
tests/ pytest suite
frontend/src/pages/ React pages
docs/ ER, normalization, measurements, viva prep
postman/ API collection


## Security

Bcrypt password hashing, JWT authentication, role-based authorization,
Pydantic input validation, parameterized queries throughout. No plaintext
passwords are stored.
