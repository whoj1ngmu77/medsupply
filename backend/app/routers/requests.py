from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.request import Allocation, EmergencyRequest
from app.models.user import UserAccount
from app.repositories.common import paginate
from app.schemas.request import (AllocationOut, AllocationResult,
                                 RequestCreate, RequestOut)
from app.services.allocation_service import (AllocationError,
                                             allocate_request,
                                             cancel_allocation)

router = APIRouter(prefix="/requests", tags=["Emergency Requests"])

COORDINATOR = require_roles("ADMIN", "EMERGENCY_COORDINATOR")
RAISER = require_roles("ADMIN", "EMERGENCY_COORDINATOR", "HOSPITAL_STAFF")


@router.get("", dependencies=[Depends(get_current_user)])
def list_requests(
    db: Session = Depends(get_db),
    hospital_id: int | None = None,
    medicine_id: int | None = None,
    request_status: str | None = None,
    priority: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(EmergencyRequest)
    if hospital_id:
        stmt = stmt.where(EmergencyRequest.hospital_id == hospital_id)
    if medicine_id:
        stmt = stmt.where(EmergencyRequest.medicine_id == medicine_id)
    if request_status:
        stmt = stmt.where(EmergencyRequest.request_status == request_status)
    if priority:
        stmt = stmt.where(EmergencyRequest.priority == priority)
    stmt = stmt.order_by(EmergencyRequest.request_id.desc())

    rows, total = paginate(db, stmt, limit, offset)
    return {"items": [RequestOut.model_validate(r) for r in rows],
            "total": total, "limit": limit, "offset": offset}


@router.get("/queue", dependencies=[Depends(get_current_user)])
def allocation_queue(db: Session = Depends(get_db),
                     limit: int = Query(default=50, ge=1, le=200)):
    """Pending/partial requests, most urgent first.

    Priority is ordered semantically, not alphabetically — CRITICAL
    must outrank HIGH, which a plain ORDER BY priority would get wrong.
    """
    rows = db.execute(text("""
        SELECT r.request_id, h.name AS hospital_name, m.name AS medicine_name,
               r.qty_requested, r.qty_fulfilled,
               r.qty_requested - r.qty_fulfilled AS qty_outstanding,
               r.priority, r.request_status, r.requested_at, r.required_by
        FROM emergency_request r
        JOIN hospital h ON h.hospital_id = r.hospital_id
        JOIN medicine m ON m.medicine_id = r.medicine_id
        WHERE r.request_status IN ('PENDING', 'PARTIAL')
        ORDER BY CASE r.priority
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3 ELSE 4 END,
                 r.required_by ASC NULLS LAST,
                 r.requested_at ASC
        LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{request_id}", response_model=RequestOut,
            dependencies=[Depends(get_current_user)])
def get_request(request_id: int, db: Session = Depends(get_db)):
    row = db.get(EmergencyRequest, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    return row


@router.get("/{request_id}/allocations",
            dependencies=[Depends(get_current_user)])
def request_allocations(request_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT a.allocation_id, a.batch_id, b.batch_number, b.expiry_date,
               w.name AS warehouse_name, a.qty_allocated, a.allocated_at,
               a.allocation_status
        FROM allocation a
        JOIN inventory_batch b ON b.batch_id = a.batch_id
        JOIN warehouse w ON w.warehouse_id = b.warehouse_id
        WHERE a.request_id = :rid
        ORDER BY a.allocated_at
    """), {"rid": request_id}).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=RequestOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(RAISER)])
def create_request(payload: RequestCreate,
                   db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    # Hospital staff may only raise requests for their own hospital.
    if user.role == "HOSPITAL_STAFF" and user.hospital_id != payload.hospital_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You may only raise requests for your own hospital")

    row = EmergencyRequest(**payload.model_dump(), raised_by=user.user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{request_id}/allocate", response_model=AllocationResult,
             dependencies=[Depends(COORDINATOR)])
def allocate(request_id: int,
             db: Session = Depends(get_db),
             user: UserAccount = Depends(get_current_user)):
    """Run the ACID allocation transaction.

    The try/except IS the transaction boundary: commit on success,
    rollback on any failure. Nothing partial is ever persisted.
    """
    try:
        result = allocate_request(db, request_id, actor_user_id=user.user_id)
        db.commit()
        return result
    except AllocationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except OperationalError as exc:
        db.rollback()
        msg = str(exc.orig).lower() if exc.orig else ""
        if "lock timeout" in msg or "canceling statement" in msg:
            raise HTTPException(
                status.HTTP_423_LOCKED,
                "Inventory is locked by another allocation. Retry shortly.")
        if "deadlock" in msg:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Deadlock detected; this transaction was chosen as victim.")
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/allocations/{allocation_id}/cancel",
             dependencies=[Depends(COORDINATOR)])
def cancel(allocation_id: int,
           db: Session = Depends(get_db),
           user: UserAccount = Depends(get_current_user)):
    try:
        result = cancel_allocation(db, allocation_id,
                                   actor_user_id=user.user_id)
        db.commit()
        return result
    except AllocationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except Exception:
        db.rollback()
        raise


@router.get("/{request_id}/events", dependencies=[Depends(get_current_user)])
def request_events(request_id: int, db: Session = Depends(get_db)):
    """Audit trail. Supports the Phase 9 recovery narrative."""
    rows = db.execute(text("""
        SELECT event_id, batch_id, event_type, old_value, new_value,
               txn_note, actor_type, occurred_at
        FROM allocation_event
        WHERE request_id = :rid
        ORDER BY event_id
    """), {"rid": request_id}).mappings().all()
    return [dict(r) for r in rows]
