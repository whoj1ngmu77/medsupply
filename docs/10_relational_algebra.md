# Relational Algebra — MedSupply

Eight queries from the running system, expressed in both SQL and
relational algebra. Notation: σ selection, π projection, ⋈ natural join,
⋈θ theta join, ⟕ left outer join, ρ rename, γ grouping/aggregation,
× Cartesian product, ∪ union, − difference, ÷ division.

---

## Q1 — Batches in a warehouse for a medicine

**Endpoint:** `GET /inventory?warehouse_id=5&medicine_id=12`

```sql
SELECT batch_id, batch_number, qty_on_hand, expiry_date
FROM inventory_batch
WHERE warehouse_id = 5 AND medicine_id = 12;
```

**RA:**

π batch_id, batch_number, qty_on_hand, expiry_date
( σ warehouse_id = 5 ∧ medicine_id = 12 ( inventory_batch ) )


Selection is applied before projection. The optimizer would do this
regardless — see the selection-pushdown demo.

---

## Q2 — Available (unexpired, unreserved) stock

**View:** `v_available_inventory`

```sql
SELECT b.batch_id, w.name, m.name, b.qty_on_hand - b.qty_reserved
FROM inventory_batch b
JOIN warehouse w ON w.warehouse_id = b.warehouse_id
JOIN medicine  m ON m.medicine_id  = b.medicine_id
WHERE b.expiry_date > CURRENT_DATE;
```

**RA:**

π b.batch_id, w.name, m.name, (b.qty_on_hand − b.qty_reserved)
( σ b.expiry_date > today
( ρ_b(inventory_batch) ⋈_{b.warehouse_id = w.warehouse_id}
ρ_w(warehouse)
⋈_{b.medicine_id = m.medicine_id} ρ_m(medicine) ) )


The arithmetic in the projection is an *extended* projection —
strict relational algebra allows only attribute lists.

---

## Q3 — FEFO batch selection (the allocation hot path)

**Used by:** `POST /requests/{id}/allocate`

```sql
SELECT batch_id, qty_on_hand - qty_reserved AS avail
FROM inventory_batch
WHERE medicine_id = 12
  AND expiry_date > CURRENT_DATE
  AND (qty_on_hand - qty_reserved) > 0
ORDER BY expiry_date ASC, batch_id ASC;
```

**RA:**

τ expiry_date, batch_id
( π batch_id, (qty_on_hand − qty_reserved)
( σ medicine_id = 12
∧ expiry_date > today
∧ (qty_on_hand − qty_reserved) > 0 ( inventory_batch ) ) )


τ (tau) is the sort operator — an extension, since relational algebra
operates on sets, which are unordered. Sorting is a physical concern
that pure RA does not express.

---

## Q4 — Requests with fulfilment totals

**View:** `v_request_fulfilment`

```sql
SELECT r.request_id, h.name, SUM(a.qty_allocated)
FROM emergency_request r
JOIN hospital h ON h.hospital_id = r.hospital_id
LEFT JOIN allocation a ON a.request_id = r.request_id
GROUP BY r.request_id, h.name;
```

**RA:**

γ r.request_id, h.name; SUM(a.qty_allocated) → total
( ( ρ_r(emergency_request) ⋈{r.hospital_id = h.hospital_id} ρ_h(hospital) )
⟕{r.request_id = a.request_id} ρ_a(allocation) )


The LEFT OUTER JOIN (⟕) preserves requests with no allocations, which
an inner join would drop.

---

## Q5 — Hospitals that have requested EVERY life-saving medicine

**Division — the operator with no direct SQL keyword.**

```sql
SELECT h.hospital_id, h.name
FROM hospital h
WHERE NOT EXISTS (
    SELECT m.medicine_id FROM medicine m
    WHERE m.criticality = 'LIFE_SAVING'
      AND NOT EXISTS (
          SELECT 1 FROM emergency_request r
          WHERE r.hospital_id = h.hospital_id
            AND r.medicine_id = m.medicine_id));
```

**RA:**

π hospital_id, medicine_id ( emergency_request )
÷ π medicine_id ( σ criticality = 'LIFE_SAVING' ( medicine ) )


Division answers "for all" questions. SQL has no `DIVIDE`, so it is
written as a double-negation: *there is no life-saving medicine that
this hospital has not requested*. Being able to map between the two
forms is a standard viva question.

Expanded, division is:

R ÷ S = π_A(R) − π_A( ( π_A(R) × S ) − R )


---

## Q6 — Medicines requested but never supplied (set difference)

```sql
SELECT DISTINCT medicine_id FROM emergency_request
EXCEPT
SELECT DISTINCT medicine_id FROM supply_consignment;
```

**RA:**

π medicine_id ( emergency_request ) − π medicine_id ( supply_consignment )


Direct correspondence: SQL's EXCEPT is RA's −.

---

## Q7 — Critical shortages (the rewritten view)

**View:** `v_critical_shortage` — see docs/05_indexing_report.md for why
this shape matters.

```sql
WITH avail AS (
    SELECT medicine_id, SUM(qty_on_hand - qty_reserved) AS total
    FROM inventory_batch WHERE expiry_date > CURRENT_DATE
    GROUP BY medicine_id)
SELECT m.medicine_id, m.name, COALESCE(a.total, 0)
FROM medicine m LEFT JOIN avail a ON a.medicine_id = m.medicine_id
WHERE m.criticality IN ('ESSENTIAL','LIFE_SAVING')
  AND COALESCE(a.total, 0) < 500;
```

**RA:**

Let A ← γ medicine_id; SUM(qty_on_hand − qty_reserved) → total
( σ expiry_date > today ( inventory_batch ) )

σ total < 500
( π m.medicine_id, m.name, A.total
( σ m.criticality ∈ {ESSENTIAL, LIFE_SAVING} ( ρ_m(medicine) )
⟕_{m.medicine_id = A.medicine_id} A ) )


**Note the shape.** Aggregating into A *before* the join is the
optimization described in the indexing report. The original version
joined medicine to both `inventory_batch` and `emergency_request`
directly, producing a Cartesian-like fan-out of 127 million tuples.
In RA terms: γ applied after a multi-way join over two independent
one-to-many relationships multiplies cardinalities; γ applied to each
branch first does not.

---

## Q8 — Allocation join for a request

**Endpoint:** `GET /requests/{id}/allocations`

```sql
SELECT a.allocation_id, b.batch_number, w.name, a.qty_allocated
FROM allocation a
JOIN inventory_batch b ON b.batch_id = a.batch_id
JOIN warehouse w ON w.warehouse_id = b.warehouse_id
WHERE a.request_id = 42;
```

**RA:**

π a.allocation_id, b.batch_number, w.name, a.qty_allocated
( σ a.request_id = 42
( ρ_a(allocation) ⋈_{a.batch_id = b.batch_id} ρ_b(inventory_batch)
⋈_{b.warehouse_id = w.warehouse_id} ρ_w(warehouse) ) )


---

## Operators used

| Operator | Symbol | Where used |
|---|---|---|
| Selection | σ | Q1, Q2, Q3, Q7, Q8 |
| Projection | π | all |
| Natural / theta join | ⋈ | Q2, Q4, Q8 |
| Left outer join | ⟕ | Q4, Q7 |
| Rename | ρ | Q2, Q4, Q7, Q8 |
| Aggregation | γ | Q4, Q7 |
| Division | ÷ | Q5 |
| Set difference | − | Q5 (expansion), Q6 |
| Cartesian product | × | Q5 (expansion) |
| Sort (extension) | τ | Q3 |

## What relational algebra cannot express

- **Ordering** — RA works on sets. τ is an extension, not core algebra.
- **Aggregation** — γ is also an extension; Codd's original algebra had no aggregates.
- **Recursion** — no fixed-point operator (SQL adds `WITH RECURSIVE`).
- **NULL semantics** — RA assumes total relations; SQL's three-valued logic has no clean algebraic counterpart.
- **Updates** — RA is a query language only.

Being able to name what the formalism *cannot* do is worth as much in a
viva as being able to translate the queries it can.
