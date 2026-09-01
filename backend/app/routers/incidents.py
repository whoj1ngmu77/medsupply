from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.mongo import mongo_db
from app.db.postgres import get_db
from app.models.user import UserAccount
from app.repositories import incident_repo as repo
from app.schemas.incident import (IncidentCreate, IncidentTimelineEntry,
                                  IncidentUpdate)

router = APIRouter(prefix="/incidents", tags=["Emergency Incidents"])

COORDINATOR = require_roles("ADMIN", "EMERGENCY_COORDINATOR")


@router.get("", dependencies=[Depends(get_current_user)])
async def list_incidents(
    incident_type: str | None = None,
    severity: str | None = None,
    incident_status: str | None = None,
    hospital_id: int | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
):
    return await repo.list_incidents(
        mongo_db, incident_type, severity, incident_status,
        hospital_id, search, limit, skip)


@router.get("/stats", dependencies=[Depends(get_current_user)])
async def incident_stats():
    return await repo.stats(mongo_db)


@router.get("/schema-variation", dependencies=[Depends(get_current_user)])
async def schema_variation():
    """Evidence that documents genuinely differ in shape.

    Returns one sample per incident type so the differing `details`
    payloads can be compared side by side.
    """
    samples = {}
    for t in ["FLOOD", "CHEMICAL_SPILL", "MASS_CASUALTY",
              "DISEASE_OUTBREAK", "FIRE", "EARTHQUAKE"]:
        doc = await mongo_db["incidents"].find_one({"incident_type": t})
        if doc:
            samples[t] = {
                "title": doc.get("title"),
                "detail_fields": sorted(doc.get("details", {}).keys()),
                "details": doc.get("details"),
            }
    return {
        "samples": samples,
        "argument": (
            "These payloads share no common field set. In PostgreSQL this "
            "would require a wide table that is ~90% NULL, an EAV table "
            "that loses all typing, or one table per incident type. The "
            "document model stores each shape natively."),
    }


@router.get("/{incident_id}", dependencies=[Depends(get_current_user)])
async def get_incident(incident_id: str):
    try:
        doc = await repo.get(mongo_db, incident_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return doc


@router.get("/{incident_id}/timeline", dependencies=[Depends(get_current_user)])
async def timeline(incident_id: str):
    return await repo.get_timeline(mongo_db, incident_id)


@router.get("/{incident_id}/linked-requests",
            dependencies=[Depends(get_current_user)])
def linked_requests(incident_id: str, db: Session = Depends(get_db)):
    """Cross-database join, performed in the APPLICATION layer.

    PostgreSQL cannot enforce or traverse a reference into MongoDB.
    This is the honest cost of polyglot persistence.
    """
    rows = db.execute(text("""
        SELECT r.request_id, h.name AS hospital_name, m.name AS medicine_name,
               r.qty_requested, r.qty_fulfilled, r.priority, r.request_status
        FROM emergency_request r
        JOIN hospital h ON h.hospital_id = r.hospital_id
        JOIN medicine m ON m.medicine_id = r.medicine_id
        WHERE r.incident_id = :iid
        ORDER BY r.request_id
    """), {"iid": incident_id}).mappings().all()
    return {
        "incident_id": incident_id,
        "requests": [dict(r) for r in rows],
        "note": ("Joined in the application layer. No FK constraint exists "
                 "across the database boundary, so referential integrity "
                 "here is the application's responsibility."),
    }


@router.post("", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(COORDINATOR)])
async def create_incident(payload: IncidentCreate,
                          user: UserAccount = Depends(get_current_user)):
    data = payload.model_dump()
    data["reported_by"] = data.get("reported_by") or user.username
    return await repo.create(mongo_db, data)


@router.patch("/{incident_id}", dependencies=[Depends(COORDINATOR)])
async def update_incident(incident_id: str, payload: IncidentUpdate):
    try:
        doc = await repo.update(mongo_db, incident_id,
                                payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return doc


@router.post("/{incident_id}/timeline", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(COORDINATOR)])
async def add_timeline(incident_id: str, entry: IncidentTimelineEntry,
                       user: UserAccount = Depends(get_current_user)):
    data = entry.model_dump()
    data["author"] = data.get("author") or user.username
    return await repo.add_timeline_entry(mongo_db, incident_id, data)


@router.post("/{incident_id}/link-request/{request_id}",
             dependencies=[Depends(COORDINATOR)])
def link_request(incident_id: str, request_id: int,
                 db: Session = Depends(get_db)):
    """Attach a PostgreSQL request to a MongoDB incident.

    Validation is manual: no FK can enforce this.
    """
    exists = db.execute(text(
        "SELECT request_id FROM emergency_request WHERE request_id = :r"),
        {"r": request_id}).scalar_one_or_none()
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    db.execute(text(
        "UPDATE emergency_request SET incident_id = :i WHERE request_id = :r"),
        {"i": incident_id, "r": request_id})
    db.commit()
    return {"request_id": request_id, "incident_id": incident_id,
            "message": "Linked (application-enforced, not an FK)"}


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles("ADMIN"))])
async def delete_incident(incident_id: str):
    try:
        ok = await repo.delete(mongo_db, incident_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
