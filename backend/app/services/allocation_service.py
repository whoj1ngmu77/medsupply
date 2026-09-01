"""The ACID allocation transaction — the core of MedSupply.

ATOMICITY    All reservations, allocation rows, and the request status
             update commit together or not at all.
CONSISTENCY  chk_reserved_le_onhand (Phase 3) is the database-level
             backstop; the service also enforces the semantic rules
             that CHECK constraints cannot express.
ISOLATION    READ COMMITTED + SELECT ... FOR UPDATE. The explicit row
             lock is what prevents the lost update; the isolation level
             alone does not.
DURABILITY   PostgreSQL WAL. Once COMMIT returns, the reservation
             survives a crash.
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("medsupply.allocation")


class AllocationError(Exception):
    """Business-rule failure. Triggers rollback."""


def allocate_request(db: Session, request_id: int,
                     actor_user_id: int | None = None,
                     lock_timeout_ms: int = 5000) -> dict:
    """Allocate inventory to a request, FEFO, inside one transaction.

    The caller supplies the Session; this function does not commit.
    The router owns the transaction boundary so that a failure anywhere
    rolls back everything.
    """
    # Bound the lock wait. Without this, a stuck transaction blocks
    # this one forever instead of failing cleanly.
    db.execute(text(f"SET LOCAL lock_timeout = '{int(lock_timeout_ms)}ms'"))

    # ---- 1. Lock the request row itself ----
    # Prevents two coordinators allocating the same request concurrently.
    req = db.execute(text("""
        SELECT request_id, medicine_id, qty_requested, qty_fulfilled,
               request_status
        FROM emergency_request
        WHERE request_id = :rid
        FOR UPDATE
    """), {"rid": request_id}).mappings().one_or_none()

    if req is None:
        raise AllocationError(f"Request {request_id} not found")

    if req["request_status"] in ("ALLOCATED", "DISPATCHED",
                                "DELIVERED", "REJECTED"):
        raise AllocationError(
            f"Request {request_id} is {req['request_status']}; "
            "no further allocation possible")

    outstanding = req["qty_requested"] - req["qty_fulfilled"]
    if outstanding <= 0:
        raise AllocationError(f"Request {request_id} is already fulfilled")

    # ---- 2. Lock candidate batches, FEFO ----
    # FOR UPDATE here is the critical line. Ordering by batch_id after
    # expiry_date gives a DETERMINISTIC lock order, which is what
    # prevents deadlock between two concurrent allocations of the same
    # medicine (see docs/07_transactions_concurrency.md).
    batches = db.execute(text("""
        SELECT batch_id, warehouse_id, batch_number, qty_on_hand,
               qty_reserved, expiry_date,
               (qty_on_hand - qty_reserved) AS qty_available
        FROM inventory_batch
        WHERE medicine_id = :mid
          AND expiry_date > CURRENT_DATE
          AND (qty_on_hand - qty_reserved) > 0
        ORDER BY expiry_date ASC, batch_id ASC
        FOR UPDATE
    """), {"mid": req["medicine_id"]}).mappings().all()

    if not batches:
        raise AllocationError(
            f"No unexpired stock available for medicine {req['medicine_id']}")

    # ---- 3. Consume batches until satisfied ----
    remaining = outstanding
    lines = []

    for b in batches:
        if remaining <= 0:
            break

        take = min(remaining, b["qty_available"])
        if take <= 0:
            continue

        # Reserve. The WHERE clause re-checks availability as a second
        # line of defence; combined with the row lock it is belt and braces.
        result = db.execute(text("""
            UPDATE inventory_batch
            SET qty_reserved = qty_reserved + :take
            WHERE batch_id = :bid
              AND (qty_on_hand - qty_reserved) >= :take
        """), {"take": take, "bid": b["batch_id"]})

        if result.rowcount != 1:
            raise AllocationError(
                f"Concurrent modification detected on batch {b['batch_id']}")

        db.execute(text("""
            INSERT INTO allocation (request_id, batch_id, qty_allocated,
                                    allocated_by, allocation_status)
            VALUES (:rid, :bid, :qty, :uid, 'RESERVED')
            ON CONFLICT (request_id, batch_id) DO UPDATE
            SET qty_allocated = allocation.qty_allocated + EXCLUDED.qty_allocated
        """), {"rid": request_id, "bid": b["batch_id"],
               "qty": take, "uid": actor_user_id})

        db.execute(text("""
            INSERT INTO allocation_event (request_id, batch_id, event_type,
                                          old_value, new_value, txn_note,
                                          actor_user_id, actor_type)
            VALUES (:rid, :bid, 'RESERVE', :old, :new,
                    'FEFO allocation, row-locked', :uid,
                    CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
        """), {"rid": request_id, "bid": b["batch_id"],
               "old": str(b["qty_reserved"]),
               "new": str(b["qty_reserved"] + take),
               "uid": actor_user_id})

        lines.append({
            "batch_id": b["batch_id"],
            "batch_number": b["batch_number"],
            "warehouse_id": b["warehouse_id"],
            "qty_allocated": take,
            "expiry_date": str(b["expiry_date"]),
        })
        remaining -= take

    allocated_now = outstanding - remaining
    if allocated_now == 0:
        raise AllocationError("No stock could be allocated")

    # ---- 4. Update the request ----
    new_fulfilled = req["qty_fulfilled"] + allocated_now
    new_status = ("ALLOCATED" if new_fulfilled >= req["qty_requested"]
                  else "PARTIAL")

    db.execute(text("""
        UPDATE emergency_request
        SET qty_fulfilled = :qf, request_status = :st
        WHERE request_id = :rid
    """), {"qf": new_fulfilled, "st": new_status, "rid": request_id})

    logger.info("Allocated %s units to request %s across %s batches",
                allocated_now, request_id, len(lines))

    return {
        "request_id": request_id,
        "qty_requested": req["qty_requested"],
        "qty_allocated": allocated_now,
        "qty_outstanding": req["qty_requested"] - new_fulfilled,
        "status": new_status,
        "lines": lines,
        "message": (f"Allocated {allocated_now} units across {len(lines)} "
                    f"batch(es). Status: {new_status}"),
    }


def cancel_allocation(db: Session, allocation_id: int,
                      actor_user_id: int | None = None) -> dict:
    """Release a reservation. Same locking discipline, reverse direction."""
    db.execute(text("SET LOCAL lock_timeout = '5000ms'"))

    alloc = db.execute(text("""
        SELECT allocation_id, request_id, batch_id, qty_allocated,
               allocation_status
        FROM allocation
        WHERE allocation_id = :aid
        FOR UPDATE
    """), {"aid": allocation_id}).mappings().one_or_none()

    if alloc is None:
        raise AllocationError(f"Allocation {allocation_id} not found")
    if alloc["allocation_status"] != "RESERVED":
        raise AllocationError(
            f"Cannot cancel an allocation in state {alloc['allocation_status']}")

    db.execute(text("""
        SELECT batch_id FROM inventory_batch
        WHERE batch_id = :bid FOR UPDATE
    """), {"bid": alloc["batch_id"]})

    db.execute(text("""
        UPDATE inventory_batch
        SET qty_reserved = qty_reserved - :qty
        WHERE batch_id = :bid
    """), {"qty": alloc["qty_allocated"], "bid": alloc["batch_id"]})

    db.execute(text("""
        UPDATE allocation SET allocation_status = 'CANCELLED'
        WHERE allocation_id = :aid
    """), {"aid": allocation_id})

    db.execute(text("""
        UPDATE emergency_request
        SET qty_fulfilled = qty_fulfilled - :qty,
            request_status = CASE
                WHEN qty_fulfilled - :qty <= 0 THEN 'PENDING'
                ELSE 'PARTIAL' END
        WHERE request_id = :rid
    """), {"qty": alloc["qty_allocated"], "rid": alloc["request_id"]})

    db.execute(text("""
        INSERT INTO allocation_event (request_id, batch_id, event_type,
                                      new_value, txn_note, actor_user_id,
                                      actor_type)
        VALUES (:rid, :bid, 'CANCEL', :qty,
                'Reservation released', :uid,
                CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
    """), {"rid": alloc["request_id"], "bid": alloc["batch_id"],
           "qty": str(alloc["qty_allocated"]), "uid": actor_user_id})

    return {"allocation_id": allocation_id,
            "released": alloc["qty_allocated"],
            "message": "Reservation released"}
