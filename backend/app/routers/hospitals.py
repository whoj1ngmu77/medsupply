from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.core import Hospital
from app.repositories.common import paginate
from app.schemas.core import HospitalCreate, HospitalOut, HospitalUpdate

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])

ADMIN_ONLY = require_roles("ADMIN")
STAFF = require_roles("ADMIN", "EMERGENCY_COORDINATOR", "HOSPITAL_STAFF")


@router.get("", dependencies=[Depends(get_current_user)])
def list_hospitals(
    db: Session = Depends(get_db),
    city: str | None = None,
    emergency_level: str | None = None,
    q: str | None = Query(default=None, description="Name search"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Hospital)
    if city:
        stmt = stmt.where(Hospital.city == city)
    if emergency_level:
        stmt = stmt.where(Hospital.emergency_level == emergency_level)
    if q:
        stmt = stmt.where(Hospital.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Hospital.hospital_id)

    rows, total = paginate(db, stmt, limit, offset)
    return {
        "items": [HospitalOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{hospital_id}", response_model=HospitalOut,
            dependencies=[Depends(get_current_user)])
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    row = db.get(Hospital, hospital_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found")
    return row


@router.post("", response_model=HospitalOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(ADMIN_ONLY)])
def create_hospital(payload: HospitalCreate, db: Session = Depends(get_db)):
    row = Hospital(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{hospital_id}", response_model=HospitalOut,
              dependencies=[Depends(STAFF)])
def update_hospital(hospital_id: int, payload: HospitalUpdate,
                    db: Session = Depends(get_db)):
    row = db.get(Hospital, hospital_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{hospital_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(ADMIN_ONLY)])
def delete_hospital(hospital_id: int, db: Session = Depends(get_db)):
    row = db.get(Hospital, hospital_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found")
    db.delete(row)
    db.commit()
