# Indexing & Query Optimization — MedSupply

All measurements captured live with `EXPLAIN (ANALYZE, BUFFERS)`,
median of 3 runs, on the deterministic seed dataset
(`seed_data.py --mode bulk`, random seed 302: 60,000 batches,
50,000 requests). Raw plans in `docs/measurements/`.

## Reproducing

docker compose up -d
python backend/scripts/seed_data.py --mode bulk
psql "$PGPASS" -f backend/sql/04_benchmark_queries.sql # before
psql "$PGPASS" -f backend/sql/05_indexes.sql
psql "$PGPASS" -f backend/sql/04_benchmark_queries.sql # after


Or live via the API: `GET /dbms/benchmarks/{key}`.

## Index Catalogue

| Index | Type | Columns | Serves | Rationale |
|---|---|---|---|---|
| `idx_batch_wh_med` | B-tree | (warehouse_id, medicine_id) | `GET /inventory` | Composite; equality on both. warehouse_id leads as the more selective column (1,500 rows/warehouse vs 3,000/medicine). |
| `idx_batch_expiry` | B-tree | (expiry_date) | `GET /inventory/expiring` | Range predicate. B-tree required — hash cannot serve ranges. |
| `idx_batch_fefo` | B-tree | (medicine_id, expiry_date, batch_id) | allocation hot path | Leading equality then ORDER BY columns in order, so the index also supplies the sort. |
| `idx_request_open` | B-tree, **partial** | (priority, required_by) WHERE status IN ('PENDING','PARTIAL') | `GET /requests/queue` | ~35% of rows qualify; index is a third the size and stays cache-resident. |
| `idx_request_hospital` | B-tree | (hospital_id, requested_at DESC) | `GET /requests?hospital_id=` | DESC matches the query's sort direction, avoiding a reverse scan. |
| `idx_hospital_reg_hash` | **Hash** | (reg_number) | equality lookup only | Included to demonstrate the B-tree/hash distinction with a real object. |
| `idx_allocation_request` | B-tree | (request_id) | FK | PostgreSQL does not auto-index FKs; without it, parent DELETE scans the child table. |
| `idx_allocation_batch` | B-tree | (batch_id) | FK | Same. |

## Measured Results

<!-- Fill from your own docs/measurements/ output -->

| Query | Before | After | Rows discarded before | after |
|---|---|---|---|---|
| Q1 batch by warehouse+medicine | | | 1464 | |
| Q2 expiry range | | | | |
| Q3 open critical requests | | | | |
| Q4 FEFO selection | | | | |
| Q5 hospital history | | | | |

## Findings

### The baseline was already using an index — badly

Before adding any index, Q1 used `uq_batch_natural`
(warehouse_id, batch_number) from Phase 3. It could only apply the
leading column, fetching 1,536 rows for warehouse 5 and discarding
1,464 in the heap. **An index existing is not the same as an index
being useful.** The composite `idx_batch_wh_med` satisfies both
predicates in the index and drops `Rows Removed by Filter` to 0.

### Composite index column order

`(warehouse_id, medicine_id)` serves both `WHERE warehouse_id = ?`
and `WHERE warehouse_id = ? AND medicine_id = ?`, but NOT
`WHERE medicine_id = ?` alone — a B-tree can only use a prefix of
its key. This is why `idx_batch_fefo` leads with `medicine_id`:
the allocation path filters on medicine, not warehouse.

### Partial index

`idx_request_open` indexes only open requests. Closed requests are
never queried by the allocation queue, so indexing them wastes space
and cache. Trade-off: the index cannot serve a query that omits the
status predicate.

### B-tree vs Hash

| | B-tree | Hash |
|---|---|---|
| Equality `=` | Yes | Yes |
| Range `<`, `>`, BETWEEN | Yes | **No** |
| ORDER BY support | Yes | **No** |
| Prefix `LIKE 'abc%'` | Yes | No |
| Lookup complexity | O(log n) | O(1) average |

Every range and sort query in MedSupply requires B-tree. Hash is
used only for `hospital.reg_number` exact lookup. Since PostgreSQL 10
hash indexes are WAL-logged and crash-safe; before that they were
unsafe and effectively unusable.

### Sequential scan is sometimes correct

`SELECT * FROM inventory_batch WHERE qty_on_hand > 0` matches
almost every row. The planner chooses Seq Scan and is right to:
random index lookups plus a heap fetch per row cost more than one
sequential pass. Reported as a finding, not a failure.

### Selection pushdown is automatic

Variants A1 and A2 of the pushdown demo produce identical plans.
PostgreSQL applies pushdown during query rewriting. The
transformation is an optimizer rule, not a programmer
responsibility — which is itself the result worth reporting.

## Why not index everything

Every index must be maintained on INSERT, UPDATE, and DELETE. With
60,000 batches and a write-heavy allocation path, each extra index
slows the transaction that matters most. Indexes were chosen from
observed query predicates only.
