# MedSupply — Emergency Medical Supply Management System

**BCSE302L Database Systems** · Vellore Institute of Technology

A database systems project built around one hard problem: **two hospitals
must never be allocated the same units of scarce medicine.** Everything
else — the schema, the indexes, the concurrency control, the frontend —
exists to make that guarantee visible and testable.

---

## What this is

Not a hospital CRUD app. The database work is the project:

- **ACID allocation transaction** with FEFO batch selection and
  `SELECT … FOR UPDATE` row locking
- **Live DBMS demonstrations** — index benchmarks, a reproducible lost
  update, a real deadlock with wait-for graph, rollback and savepoints,
  all measured against the running database
- **Polyglot persistence** — PostgreSQL for transactional core,
  MongoDB for schema-variable incident records, with the trade-off
  documented rather than glossed over

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind v4, Recharts |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Relational | PostgreSQL 16 |
| Document | MongoDB 7 (Motor) |
| Auth | JWT + bcrypt (cost 12) |
| Testing | pytest, Postman |

## Quick start

git clone <repo-url> && cd medsupply
cp backend/.env.example backend/.env # fill in the values
./setup.sh # databases + schema + seed


Then two terminals:

cd backend && python -m uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev


Open http://localhost:5173 · login `admin` / `admin@12345`

**Full stack in Docker** (no local Python or Node needed):

docker compose -f docker-compose.full.yml up -d --build
docker exec medsupply_api python scripts/seed_data.py --mode bulk
docker exec medsupply_api python scripts/set_passwords.py
docker exec medsupply_api python scripts/seed_incidents.py


Frontend on http://localhost:3000

## Demo accounts

| Username | Password | Role |
|---|---|---|
| admin | admin@12345 | ADMIN |
| coordinator | coord@12345 | EMERGENCY_COORDINATOR |
| hosp1 | hosp1@12345 | HOSPITAL_STAFF |
| wh1 | wh1@12345 | WAREHOUSE_STAFF |

Dev credentials only.

## Syllabus coverage

| Topic | Where |
|---|---|
| ER / EER modelling | `docs/01_er_diagram.md` |
| Relational model, keys | `docs/02_relational_schema.md` |
| Functional dependencies | `docs/03_functional_dependencies.md` |
| 1NF → BCNF, 4NF | `docs/04_normalization.md` |
| Integrity constraints | `backend/sql/01_schema.sql` |
| Indexing, B+ tree, hashing | `docs/05_indexing_report.md`, DBMS Demos page |
| Relational algebra | `docs/10_relational_algebra.md` |
| Query processing & optimization | DBMS Demos → Query optimization |
| ACID transactions | `backend/app/services/allocation_service.py` |
| Serializability, 2PL | DBMS Demos → Concurrency |
| Deadlock detection | DBMS Demos → Deadlock |
| Log-based recovery | DBMS Demos → Recovery |
| NoSQL, CAP, document DBs | `docs/09_nosql_cap.md`, DBMS Demos → NoSQL |

## Headline results

All measured on the deterministic seed set (random seed 302: 60,000
batches, 50,000 requests). Raw plans in `docs/measurements/`.

**Correctness.** 100 units, requests for 70 and 50. Without locking:
120 units promised, 70 silently lost. With `FOR UPDATE`: 70 granted,
50 correctly reduced to 30. Reproducible from the DBMS Demos page.

**Indexing.** All six benchmark queries dropped `Rows Removed by Filter`
to zero. Largest speedup 38× (`idx_request_hospital`, which serves the
filter, the sort order, and the LIMIT together).

**Query rewriting.** `v_critical_shortage` fell from **10,967 ms to
11.5 ms** — a fan-out join was materialising **127,083,348 intermediate
rows** to produce 2. No index could have fixed it; only restructuring
the query could. This is the most significant optimization in the
project and it was found from a slow page, not a planned benchmark.

**Deadlock.** Reproducible cycle T1 → T2 → T1, detected after
`deadlock_timeout` (1s), victim aborted with SQLSTATE 40P01.

## Testing

cd backend && python -m pytest -v # 20 tests


`test_never_over_allocates` is the one that matters — it is the
executable form of the project's core requirement.

Postman collection with assertions: `postman/MedSupply.postman_collection.json`

## Layout

backend/
app/
services/allocation_service.py the ACID transaction
dbms/ live demonstration harnesses
routers/ models/ schemas/ repositories/
sql/ schema, indexes, views, benchmark queries
scripts/ seeding and utilities
tests/ pytest suite
frontend/src/
pages/dbms/ the demonstrations UI
pages/ CRUD and dashboard
docs/ all written deliverables
docs/measurements/ raw EXPLAIN and lab output


## Honest limitations

- Single-node PostgreSQL, so CAP does not strictly apply to it
- `emergency_request.incident_id` references MongoDB and **cannot** be
  enforced as a foreign key; integrity across that boundary is the
  application's responsibility
- Seed data is statistically plausible, not produced by running the
  allocation engine 50,000 times. The engine's correctness is
  demonstrated separately with known starting conditions
- Benchmark timings are cache-warm; `Rows Removed by Filter` and buffer
  counts are the machine-independent metrics
- JWTs are held in memory, so a page refresh logs you out. Production
  would use an httpOnly refresh cookie
