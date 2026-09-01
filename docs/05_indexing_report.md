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

| Query | Before | After | Speedup | Rows discarded (before → after) |
|---|---|---|---|---|
| Q1 batch by warehouse+medicine | Bitmap Heap on `uq_batch_natural`, 5.64 ms | Bitmap Heap on `idx_batch_wh_med`, 0.33 ms | **17×** | 1,464 → **0** |
| Q2 expiry range | Seq Scan, 5.62 ms | Bitmap Heap on `idx_batch_expiry`, 2.09 ms | 2.7× | 55,371 → **0** |
| Q3 open critical requests | Seq Scan, 6.51 ms | Bitmap Heap on `idx_request_open`, 1.11 ms | 5.9× | 48,256 → **0** |
| Q4 FEFO selection | Seq Scan, 4.38 ms | Bitmap Heap on `idx_batch_fefo`, 1.91 ms | 2.3× | 57,238 → **0** |
| Q5 hospital history | Seq Scan, 2.03 ms | **Index Scan** on `idx_request_hospital`, 0.05 ms | **38×** | 49,744 → **0** |
| Q6 shortage join | Seq Scan ×2, 13.43 ms | Seq Scan ×2, 13.16 ms | ~1× (unchanged) | 4,804 → 4,804 |

All six queries eliminated `Rows Removed by Filter` except Q6, which
was correctly left as a sequential scan (see findings).

### Q5: the best case for an index

Q5 is the only plain Index Scan and the largest speedup (38×). The
index `(hospital_id, requested_at DESC)` serves the filter, the sort
direction, AND the `LIMIT 50` — PostgreSQL reads exactly 50 index
entries and stops. No sort node, no discarded rows, no full scan.

### Q6: no improvement, and that is correct

Q6 aggregates 55,199 of 60,000 batches — 92% of the table. A
sequential scan is the right plan; `idx_medicine_criticality` was
not used because scanning 20 medicine rows is cheaper than an index
lookup. Reported as a finding, not a failure.

### Estimated cost vs actual time

Q1's estimated cost fell from 772 to 224, tracking the real
improvement. Q5's estimate stayed high (808) while actual time was
0.042 ms, because `LIMIT` short-circuits execution after 50 rows —
the planner's cost model prices the full scan it did not perform.

### A caching caveat, stated honestly

All plans show `Buffers: shared hit` and no `shared read`: the
dataset fits in PostgreSQL's buffer cache, so these timings measure
CPU and tuple-processing work, not disk I/O. On a cold cache the
gaps would be far larger. This is why `Rows Removed by Filter` is
reported as the primary metric — it is independent of cache state.

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

## Unplanned finding: fan-out join in `v_critical_shortage`

The dashboard endpoint `/analytics/overview` took **65 seconds** in
normal use. Timing each view individually isolated the cause:

| View | Time |
|---|---|
| `v_dashboard_kpis` | 2.1 ms |
| `v_requests_by_day` | 6.5 ms |
| `v_stock_by_category` | 23.0 ms |
| **`v_critical_shortage`** | **10,967 ms** |

### Cause

The original view joined `medicine` to BOTH `inventory_batch` and
`emergency_request` in a single query:

```sql
FROM medicine m
LEFT JOIN inventory_batch b   ON b.medicine_id = m.medicine_id
LEFT JOIN emergency_request r ON r.medicine_id = m.medicine_id
GROUP BY m.medicine_id, ...
```

Both are one-to-many from `medicine`, so the join produces the
**cartesian product** of the two child sets per medicine. A medicine
with 3,000 batches and 2,500 open requests generates 7.5 million
intermediate rows — which the aggregate then collapses to one. This is
a **fan-out join**, and no index can fix it: the cost is in rows
materialised before aggregation, not in how they are found.

### Fix

Aggregate each side independently in a CTE, then join the already-
reduced results:

```sql
WITH avail AS (
    SELECT medicine_id, SUM(qty_on_hand - qty_reserved) AS total_available
    FROM inventory_batch WHERE expiry_date > CURRENT_DATE
    GROUP BY medicine_id
),
open_req AS (
    SELECT medicine_id, COUNT(*) AS open_requests
    FROM emergency_request
    WHERE request_status IN ('PENDING','PARTIAL')
    GROUP BY medicine_id
)
SELECT ... FROM medicine m
LEFT JOIN avail a ON ... LEFT JOIN open_req o ON ...
```

Each table is scanned and aggregated once; the join then operates on
~22 rows per side.

### Result

| | Before | After | Improvement |
|---|---|---|---|
| `v_critical_shortage` | 10,967 ms | 11.5 ms | **954×** |
| `/analytics/overview` | ~65,000 ms | 137 ms | **474×** |

### Why this matters

Every other optimization in this report came from adding an index.
This one could not have: the query was already using indexes to find
its rows. The cost was structural — the wrong join shape. **Query
rewriting and index selection are separate tools, and rewriting is the
more powerful of the two when the plan shape itself is wrong.**

The finding also came from real usage rather than a planned benchmark,
which is how most production performance problems are actually
discovered.
