# Viva Preparation — MedSupply

Questions grouped by topic, with the honest answer and where to
demonstrate it live.

---

## The one question you must be able to answer

**"Walk me through what happens when you allocate a request."**

1. `SELECT … FOR UPDATE` on the request row — stops two coordinators
   allocating the same request
2. `SELECT … FOR UPDATE` on candidate batches, ordered by
   `(expiry_date, batch_id)` — FEFO *and* a deterministic lock order
3. Loop: `UPDATE inventory_batch SET qty_reserved = qty_reserved + n`,
   insert an `allocation` row, insert an `allocation_event`
4. Update the request's `qty_fulfilled` and status
5. Router commits; any exception anywhere rolls back everything

**Demonstrate:** Requests → Allocation queue → Allocate → Detail.

---

## Design

**Q. Why is Allocation an M:N associative entity rather than 1:N?**
A request for 500 units may draw 200 from one batch and 300 from
another. 1:N would force single-batch fulfilment and eliminate FEFO,
multi-row locking, and the concurrency problem entirely.

**Q. Why is `qty_reserved` stored rather than derived from allocations?**
Deliberate denormalization. It is the row taken `FOR UPDATE` — the
contention point. Deriving it would need an aggregate over a growing
table on every allocation. `qty_available` *is* derived (a view column)
because it is not contended.

**Q. Your 3NF relations are already in BCNF — so why does BCNF exist?**
`STOCK_CUSTODIAN(warehouse_id, category_id, custodian_id)` with
`custodian_id → warehouse_id`. `custodian_id` is a determinant but not
a superkey. It is in 3NF (`warehouse_id` is prime) but violates BCNF.

**Q. Is that decomposition dependency-preserving?**
No. `(warehouse_id, category_id) → custodian_id` can no longer be
checked in a single relation and needs a trigger. That is the classic
3NF/BCNF trade-off — BCNF guarantees losslessness, not dependency
preservation.

**Q. Why is SUPPLY_CONSIGNMENT not a 4NF violation?**
Supplier, medicine, and warehouse are *jointly* dependent — one
consignment is a single real event. An MVD requires independence.

---

## Transactions & concurrency

**Q. Where exactly is the lost update prevented?**
The `FOR UPDATE` on the batch SELECT. Isolation level alone
(READ COMMITTED) would not prevent it. **Demonstrate:** DBMS Demos →
Concurrency → Run unsafe, then Run safe.

**Q. Why READ COMMITTED, not SERIALIZABLE?**
Explicit row locks give the needed guarantee at lower cost.
SERIALIZABLE would also work but introduces serialization failures
requiring retry logic. A deliberate trade-off.

**Q. Where is two-phase locking in your code?**
Growing phase: every `FOR UPDATE` in the service. Shrinking phase: the
router's `db.commit()`. PostgreSQL uses *strict* 2PL — nothing is
released early, which also prevents cascading aborts.

**Q. Why doesn't production allocation deadlock?**
All transactions lock batches in the same order
(`expiry_date ASC, batch_id ASC`), so circular wait — one of the four
Coffman conditions — cannot form. The demo deadlocks precisely because
it reverses the order.

**Q. How does PostgreSQL detect deadlock?**
A wait-for graph cycle check triggered lazily after `deadlock_timeout`
(set to 1s here). Continuous checking would cost more than the rare
deadlock it prevents. **Demonstrate:** DBMS Demos → Deadlock.

**Q. Immediate vs deferred update?**
PostgreSQL uses immediate update with WAL undo — data pages may be
written before commit, so undo records are required. Deferred update
buffers all writes until commit: simpler recovery, unusable for long
transactions.

**Q. Is `allocation_event` your transaction log?**
No. It is an application-level audit log for business history. The WAL
is the system-level log used for crash recovery. Different purposes.

---

## Indexing & optimization

**Q. Your Q1 already used an index before you created one. Why was it slow?**
`uq_batch_natural (warehouse_id, batch_number)` from the UNIQUE
constraint. Only the leading column applied, so it fetched 1,536 rows
and discarded 1,464 in the heap. **An index existing is not the same as
an index being useful.**

**Q. Why doesn't `idx_batch_wh_med` help `WHERE medicine_id = ?` alone?**
A B-tree can only use a *prefix* of its composite key.

**Q. Why a partial index on requests?**
Only PENDING/PARTIAL rows are ever queried by the allocation queue.
Indexing the other 65% wastes space and cache. Trade-off: it cannot
serve a query that omits the status predicate.

**Q. When is a sequential scan correct?**
When selectivity is low. `qty_on_hand > 0` matches nearly every row —
random index lookups plus heap fetches cost more than one sequential
pass. Demonstrated in the optimization lab.

**Q. Why can't a hash index serve `expiry_date BETWEEN …`?**
Hashing destroys ordering; there is no way to traverse a range.

**Q. Tell me about your biggest optimization.**
`v_critical_shortage`, 10,967 ms → 11.5 ms. It joined `medicine` to
both `inventory_batch` and `emergency_request` — two independent
one-to-many relationships — producing a **fan-out** of 127,083,348
intermediate rows to yield 2. Aggregating each branch in a CTE first
reduced each side to ~21 rows. No index could have helped; the cost was
in the query's shape. The planner's estimate (116.8M) was within 9% of
actual, so this was not a statistics problem — the query genuinely
required that work as written.

---

## NoSQL

**Q. Why not JSONB in PostgreSQL instead of MongoDB?**
A fair challenge, and JSONB would work — for a single-database
deployment it would be simpler. MongoDB was chosen to demonstrate
polyglot persistence, and because incidents also need native text
search and independent scaling. Acknowledging the alternative is
stronger than pretending it doesn't exist.

**Q. Prove the schema actually varies.**
DBMS Demos → NoSQL, or Incidents page. Six incident types, no shared
`details` field. Generated from the data with `$objectToArray`, not
asserted in prose.

**Q. Is PostgreSQL CP or CA?**
Single node: CAP does not strictly apply — there is nothing to
partition. Replicated with `synchronous_commit=remote_apply`: CP.

**Q. What breaks at the database boundary?**
No FK, no cross-database transaction, application-layer joins, and a
deleted incident can orphan a request's reference. Stated openly in
`docs/09_nosql_cap.md`.

**Q. Why can't allocation live in MongoDB?**
No equivalent of `SELECT … FOR UPDATE` over a filtered, ordered set —
the exact primitive FEFO allocation depends on.

---

## Security

**Q. Why bcrypt, not SHA-256?**
Deliberately slow (cost factor 12), per-hash salt embedded, tunable as
hardware improves. SHA-256 is fast, which is exactly wrong for
passwords.

**Q. Where is SQL injection prevented?**
SQLAlchemy bound parameters throughout. **Demonstrate:** log in with
username `admin' OR '1'='1` — clean 401, treated as a literal string.

**Q. Why is `/auth/register` admin-only?**
Self-registration would let anyone mint a coordinator account and
allocate national medicine stock.

**Q. Why do wrong-username and wrong-password return the same error?**
Prevents username enumeration.

**Q. How is the password hash kept out of API responses?**
It is not a field on the `UserOut` schema. Structural, not a filter
someone can forget.

---

## Questions you should raise yourself

Volunteering a limitation before being asked is worth more than
defending one afterwards.

- FEFO can select a batch expiring tomorrow. Correct FEFO, questionable
  policy — a `expiry_date > CURRENT_DATE + 30` buffer belongs in the
  selection policy, which is separable from the transaction's correctness.
- Seed statuses are statistically plausible, not engine-produced.
- Benchmark timings are cache-warm; rows-discarded is the honest metric.
- The `STOCK_CUSTODIAN` BCNF decomposition loses a functional dependency.

---

## Live demo running order (10 minutes)

1. **Dashboard** — live KPIs from PostgreSQL views + MongoDB aggregation
2. **Requests → Allocate** — the ACID transaction, FEFO batches listed
3. **Request Detail** — allocation rows and audit trail
4. **DBMS Demos → Concurrency** — unsafe (120/100, over-allocated),
   then safe (correct). *The most important 60 seconds.*
5. **DBMS Demos → Deadlock** — wait-for cycle, victim aborted
6. **DBMS Demos → Indexing** — run a benchmark, point at
   `Rows Removed by Filter` going to zero
7. **DBMS Demos → B+ Tree** — insert keys, watch a split
8. **Incidents → Schema variation** — the MongoDB justification
