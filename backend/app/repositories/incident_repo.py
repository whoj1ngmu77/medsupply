"""MongoDB access for emergency incidents.

Uses Motor (async). Documents are schema-flexible by design: only the
envelope fields are fixed, and `details` varies per incident_type.
"""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

COLLECTION = "incidents"
TIMELINE = "incident_updates"


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValueError(f"Invalid incident id: {value}") from exc


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def ensure_indexes(db):
    """Indexes on the fixed envelope fields only.

    The variable `details` subdocument is deliberately unindexed —
    indexing fields that may not exist on most documents would create
    large sparse indexes for little benefit.
    """
    await db[COLLECTION].create_index("incident_type")
    await db[COLLECTION].create_index("severity")
    await db[COLLECTION].create_index("status")
    await db[COLLECTION].create_index([("created_at", -1)])
    await db[COLLECTION].create_index("affected_hospital_ids")
    await db[COLLECTION].create_index([("title", "text"), ("tags", "text")])
    await db[TIMELINE].create_index([("incident_id", 1), ("at", -1)])
    return await db[COLLECTION].index_information()


async def create(db, payload: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {**payload, "status": "ACTIVE",
           "created_at": now, "updated_at": now}
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def get(db, incident_id: str) -> dict | None:
    doc = await db[COLLECTION].find_one({"_id": _oid(incident_id)})
    if doc is None:
        return None
    out = _serialize(doc)
    out["timeline_count"] = await db[TIMELINE].count_documents(
        {"incident_id": incident_id})
    return out


async def list_incidents(db, incident_type=None, severity=None, status=None,
                         hospital_id=None, search=None,
                         limit=50, skip=0) -> dict:
    query = {}
    if incident_type:
        query["incident_type"] = incident_type
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status
    if hospital_id:
        query["affected_hospital_ids"] = hospital_id
    if search:
        query["$text"] = {"$search": search}

    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).sort("created_at", -1) \
                           .skip(skip).limit(limit)
    items = [_serialize(d) async for d in cursor]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


async def update(db, incident_id: str, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if v is not None}
    if not changes:
        return await get(db, incident_id)
    changes["updated_at"] = datetime.now(timezone.utc)
    result = await db[COLLECTION].find_one_and_update(
        {"_id": _oid(incident_id)}, {"$set": changes},
        return_document=True)
    return _serialize(result) if result else None


async def add_timeline_entry(db, incident_id: str, entry: dict) -> dict:
    doc = {"incident_id": incident_id,
           "at": datetime.now(timezone.utc), **entry}
    result = await db[TIMELINE].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def get_timeline(db, incident_id: str, limit: int = 100) -> list[dict]:
    cursor = db[TIMELINE].find({"incident_id": incident_id}) \
                         .sort("at", -1).limit(limit)
    return [_serialize(d) async for d in cursor]


async def delete(db, incident_id: str) -> bool:
    await db[TIMELINE].delete_many({"incident_id": incident_id})
    result = await db[COLLECTION].delete_one({"_id": _oid(incident_id)})
    return result.deleted_count == 1


async def stats(db) -> dict:
    """Aggregation pipeline — the MongoDB analogue of GROUP BY."""
    by_type = [d async for d in db[COLLECTION].aggregate([
        {"$group": {"_id": "$incident_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])]
    by_severity = [d async for d in db[COLLECTION].aggregate([
        {"$match": {"status": "ACTIVE"}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])]
    # $objectToArray inspects each document's own field set — this query
    # has no SQL equivalent, because SQL rows cannot differ in shape.
    field_variation = [d async for d in db[COLLECTION].aggregate([
        {"$project": {"incident_type": 1,
                      "detail_keys": {"$objectToArray": "$details"}}},
        {"$unwind": "$detail_keys"},
        {"$group": {"_id": {"type": "$incident_type",
                            "field": "$detail_keys.k"},
                    "count": {"$sum": 1}}},
        {"$group": {"_id": "$_id.type",
                    "fields": {"$addToSet": "$_id.field"}}},
        {"$sort": {"_id": 1}},
    ])]
    return {
        "total": await db[COLLECTION].count_documents({}),
        "active": await db[COLLECTION].count_documents({"status": "ACTIVE"}),
        "by_type": by_type,
        "by_severity_active": by_severity,
        "detail_fields_per_type": field_variation,
        "note": ("detail_fields_per_type is computed with $objectToArray, "
                 "which inspects each document's own field set. No SQL "
                 "equivalent exists — relational rows cannot differ in "
                 "shape."),
    }
