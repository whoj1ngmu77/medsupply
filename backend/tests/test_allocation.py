"""The tests that matter. These protect the core invariant."""
import pytest
from sqlalchemy import text

from app.services.allocation_service import AllocationError, allocate_request

MED = 997


def _state(db):
    return dict(db.execute(text("""
        SELECT qty_on_hand, qty_reserved FROM inventory_batch
        WHERE medicine_id = :m
    """), {"m": MED}).mappings().one())


def test_never_over_allocates(db, scenario):
    """100 units, requests for 70 and 50. Total allocated must not exceed 100."""
    allocate_request(db, scenario["req_a"], actor_user_id=1)
    db.commit()
    allocate_request(db, scenario["req_b"], actor_user_id=1)
    db.commit()

    s = _state(db)
    total = db.execute(text("""
        SELECT COALESCE(SUM(qty_allocated), 0) FROM allocation a
        JOIN emergency_request r ON r.request_id = a.request_id
        WHERE r.medicine_id = :m AND a.allocation_status = 'RESERVED'
    """), {"m": MED}).scalar_one()

    assert total <= s["qty_on_hand"], f"OVER-ALLOCATED: {total} > {s['qty_on_hand']}"
    assert total == 100
    assert s["qty_reserved"] == 100


def test_partial_allocation(db, scenario):
    """The second request gets 30, not 50."""
    allocate_request(db, scenario["req_a"], actor_user_id=1)
    db.commit()
    result = allocate_request(db, scenario["req_b"], actor_user_id=1)
    db.commit()

    assert result["qty_allocated"] == 30
    assert result["status"] == "PARTIAL"
    assert result["qty_outstanding"] == 20


def test_rollback_leaves_no_trace(db, scenario):
    """A failed allocation must change nothing."""
    before = _state(db)
    with pytest.raises(AllocationError):
        allocate_request(db, 999_999_999)
    db.rollback()
    assert _state(db) == before


def test_cannot_allocate_twice(db, scenario):
    allocate_request(db, scenario["req_a"], actor_user_id=1)
    db.commit()
    with pytest.raises(AllocationError, match="ALLOCATED"):
        allocate_request(db, scenario["req_a"], actor_user_id=1)
    db.rollback()


def test_audit_trail_written(db, scenario):
    allocate_request(db, scenario["req_a"], actor_user_id=1)
    db.commit()
    events = db.execute(text("""
        SELECT event_type, old_value, new_value FROM allocation_event
        WHERE request_id = :r
    """), {"r": scenario["req_a"]}).mappings().all()
    assert len(events) >= 1
    assert events[0]["event_type"] == "RESERVE"
    assert events[0]["old_value"] == "0"
    assert events[0]["new_value"] == "70"


def test_check_constraint_blocks_over_reservation(db, scenario):
    """The database itself is the last line of defence."""
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.execute(text("""
            UPDATE inventory_batch SET qty_reserved = qty_on_hand + 1
            WHERE batch_id = :b
        """), {"b": scenario["batch_id"]})
        db.commit()
    db.rollback()
