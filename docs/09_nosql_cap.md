# NoSQL, Polyglot Persistence & CAP — MedSupply

## Why two databases

MedSupply uses PostgreSQL for transactional core data and MongoDB for
emergency incident records. This is not decoration; each database is
used where the other would be a poor fit.

### Why incidents are NOT in PostgreSQL

Incident detail payloads genuinely differ by type. Measured from the
seeded data (`GET /incidents/schema-variation`):

| Incident type | `details` fields |
|---|---|
| FLOOD | water_level_m, evacuation_zones, people_displaced, shelters_opened, roads_impassable, rainfall_mm_24h |
| CHEMICAL_SPILL | agent, quantity_litres, exposure_radius_m, decontamination_protocol, ppe_level, wind_direction, air_quality_index |
| MASS_CASUALTY | triage_red, triage_yellow, triage_green, triage_black, vehicles_involved, extrication_required, trauma_centres_activated |
| DISEASE_OUTBREAK | pathogen, confirmed_cases, suspected_cases, r_naught, quarantine_wards, vaccination_drive, case_curve |
| EARTHQUAKE | magnitude, depth_km, aftershocks_recorded, buildings_collapsed, search_rescue_teams, trapped_estimated |

**No two types share a field.** The relational alternatives:

1. **Wide table with nulls** — 60+ columns, ~90% NULL per row, and every
   new incident type requires an `ALTER TABLE` migration.
2. **EAV** — `(incident_id, key, value)` as text. Loses all typing;
   reconstructing one incident needs a self-join per field.
3. **Table per type** — six tables, six endpoint sets, and every
   "list all incidents" query becomes a UNION.

### Why inventory is NOT in MongoDB

Allocation requires multi-row ACID transactions with row-level locking
across `inventory_batch`, `emergency_request`, and `allocation`
(Phase 6). MongoDB has multi-document transactions since 4.0, but they
require a replica set, are markedly slower, and there is no equivalent
of `SELECT ... FOR UPDATE` over a filtered, ordered set — which is
exactly the primitive the FEFO allocation depends on.

## CAP Theorem

A distributed store cannot simultaneously guarantee Consistency,
Availability, and Partition tolerance. Partitions are a fact of
networks, not a choice, so the real decision is **C vs A during a
partition**.

### PostgreSQL: CP

As deployed here (single node) CAP does not strictly apply — there is
nothing to partition. In a replicated deployment with
`synchronous_commit = remote_apply`, PostgreSQL is CP: during a
partition it refuses writes rather than allow replicas to diverge.

**Justification for MedSupply:** allocating scarce medicine is a
consistency problem. A stale read means a hospital is promised stock
another hospital already received. Availability is worth sacrificing;
correctness is not.

### MongoDB: CP by default, tunable toward AP

A replica set with `w: majority` and `readConcern: majority` is CP —
a minority partition rejects writes. Relaxing to `w: 1` with
`readPreference: secondaryPreferred` moves toward AP: reads keep
succeeding from secondaries but may be stale.

**Justification for MedSupply:** an incident report read five seconds
stale is operationally harmless. Schema flexibility and write
availability during a crisis matter more than strict consistency.

## Document database characteristics

| Characteristic | In MedSupply |
|---|---|
| Schema flexibility | FLOOD and CHEMICAL_SPILL share only envelope fields |
| Denormalization | `location` is an embedded subdocument, not an FK |
| Limited joins | `$lookup` exists but is avoided; data is embedded |
| Horizontal scaling | Native sharding (PostgreSQL needs Citus) |
| BSON | Typed values — dates, ints, ObjectId — unlike plain JSON |
| Aggregation pipeline | `$objectToArray` inspects per-document field sets; no SQL equivalent exists |

## The cost, stated honestly

`emergency_request.incident_id` holds a MongoDB ObjectId as
`VARCHAR(24)`. **PostgreSQL cannot enforce this as a foreign key.**

- Referential integrity across the boundary is the application's job
- Deleting an incident can orphan a request's reference
- The "linked requests" query is an application-layer join
  (`GET /incidents/{id}/linked-requests`), not a database join
- No transaction spans both databases

This is the real trade-off of polyglot persistence. We accept it
because the alternative — forcing variable-shape documents into a
relational schema — costs more.

## Comparison

| Aspect | PostgreSQL | MongoDB |
|---|---|---|
| Schema | Fixed, enforced by DDL | Flexible per document |
| Transactions | Full ACID, row-level locks | Multi-document since 4.0, replica set required |
| Joins | Native, optimizer-planned | `$lookup`, limited |
| Referential integrity | FK constraints | Application-enforced |
| Query language | SQL | Aggregation pipeline / MQL |
| Scaling | Vertical; horizontal via extensions | Native sharding |
| Best for | Consistent transactional data | Variable-shape documents |

## Reproducing
python backend/scripts/seed_incidents.py
curl .../incidents/schema-variation
curl .../incidents/stats
curl .../dbms/nosql/cap

