from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.mongo import mongo_db
from app.db.postgres import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/kpis", dependencies=[Depends(get_current_user)])
def kpis(db: Session = Depends(get_db)):
    """The eight headline metrics. One query, one round trip."""
    row = db.execute(text("SELECT * FROM v_dashboard_kpis")).mappings().one()
    return dict(row)


@router.get("/requests-by-day", dependencies=[Depends(get_current_user)])
def requests_by_day(db: Session = Depends(get_db),
                    days: int = Query(default=30, ge=7, le=90)):
    rows = db.execute(text("""
        SELECT day, requests, critical, pending, delivered,
               units_requested, cumulative_units
        FROM v_requests_by_day
        WHERE day >= CURRENT_DATE - make_interval(days => :d)
        ORDER BY day
    """), {"d": days}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/medicine-demand", dependencies=[Depends(get_current_user)])
def medicine_demand(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT * FROM v_medicine_demand ORDER BY total_requested DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/stock-by-category", dependencies=[Depends(get_current_user)])
def stock_by_category(db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM v_stock_by_category")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/hospital-activity", dependencies=[Depends(get_current_user)])
def hospital_activity(db: Session = Depends(get_db),
                      limit: int = Query(default=10, ge=1, le=50)):
    rows = db.execute(text("""
        SELECT * FROM v_hospital_activity
        ORDER BY activity_rank LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/warehouse-utilisation", dependencies=[Depends(get_current_user)])
def warehouse_utilisation(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT warehouse_id, warehouse_name, city, storage_capacity,
               units_stored, utilisation_pct, batch_count
        FROM v_warehouse_utilisation ORDER BY utilisation_pct DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/priority-breakdown", dependencies=[Depends(get_current_user)])
def priority_breakdown(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT priority,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE request_status = 'PENDING') AS pending,
               COUNT(*) FILTER (WHERE request_status IN ('ALLOCATED','PARTIAL'))
                   AS allocated,
               COUNT(*) FILTER (WHERE request_status = 'DELIVERED') AS delivered,
               SUM(qty_requested) AS units_requested
        FROM emergency_request
        GROUP BY priority
        ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                               WHEN 'MEDIUM' THEN 3 ELSE 4 END
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/expiry-timeline", dependencies=[Depends(get_current_user)])
def expiry_timeline(db: Session = Depends(get_db)):
    """Batches bucketed by time to expiry."""
    rows = db.execute(text("""
        SELECT
            CASE
                WHEN expiry_date <= CURRENT_DATE THEN 'Expired'
                WHEN expiry_date <= CURRENT_DATE + 30  THEN '0-30 days'
                WHEN expiry_date <= CURRENT_DATE + 90  THEN '31-90 days'
                WHEN expiry_date <= CURRENT_DATE + 180 THEN '91-180 days'
                WHEN expiry_date <= CURRENT_DATE + 365 THEN '181-365 days'
                ELSE '365+ days' END AS bucket,
            COUNT(*) AS batches,
            SUM(qty_on_hand - qty_reserved) AS units
        FROM inventory_batch
        GROUP BY bucket
        ORDER BY MIN(expiry_date)
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/allocation-efficiency", dependencies=[Depends(get_current_user)])
def allocation_efficiency(db: Session = Depends(get_db),
                          limit: int = Query(default=25, ge=1, le=100)):
    rows = db.execute(text("""
        SELECT * FROM v_allocation_efficiency
        ORDER BY last_allocation DESC LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/incident-summary", dependencies=[Depends(get_current_user)])
async def incident_summary():
    """MongoDB side of the dashboard — aggregation pipeline."""
    by_type = [d async for d in mongo_db["incidents"].aggregate([
        {"$group": {"_id": "$incident_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])]
    by_severity = [d async for d in mongo_db["incidents"].aggregate([
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
    ])]
    recent = [
        {"id": str(d["_id"]), "title": d["title"],
         "incident_type": d["incident_type"], "severity": d["severity"],
         "city": d.get("location", {}).get("city"),
         "created_at": d["created_at"]}
        async for d in mongo_db["incidents"].find({"status": "ACTIVE"})
                                            .sort("created_at", -1).limit(8)
    ]
    return {
        "total": await mongo_db["incidents"].count_documents({}),
        "active": await mongo_db["incidents"].count_documents(
            {"status": "ACTIVE"}),
        "by_type": [{"type": r["_id"], "count": r["count"]} for r in by_type],
        "by_severity": [{"severity": r["_id"], "count": r["count"]}
                        for r in by_severity],
        "recent": recent,
    }


@router.get("/overview", dependencies=[Depends(get_current_user)])
async def overview(db: Session = Depends(get_db)):
    """Everything the dashboard needs, in one call.

    Deliberately a single endpoint: eight separate fetches on page load
    would mean eight round trips and eight loading states.
    """
    kpi = dict(db.execute(text("SELECT * FROM v_dashboard_kpis"))
               .mappings().one())
    priority = [dict(r) for r in db.execute(text("""
        SELECT priority, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE request_status = 'PENDING') AS pending
        FROM emergency_request GROUP BY priority
        ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                               WHEN 'MEDIUM' THEN 3 ELSE 4 END
    """)).mappings().all()]
    categories = [dict(r) for r in db.execute(text(
        "SELECT category_name, units_available, batch_count "
        "FROM v_stock_by_category LIMIT 8")).mappings().all()]
    trend = [dict(r) for r in db.execute(text("""
        SELECT day, requests, critical, units_requested
        FROM v_requests_by_day
        WHERE day >= CURRENT_DATE - 30 ORDER BY day
    """)).mappings().all()]
    shortages = [dict(r) for r in db.execute(text(
        "SELECT medicine_name, total_available, open_requests "
        "FROM v_critical_shortage ORDER BY total_available LIMIT 8"
    )).mappings().all()]
    incidents = await mongo_db["incidents"].count_documents(
        {"status": "ACTIVE"})

    return {
        "kpis": {**kpi, "active_incidents": incidents},
        "priority_breakdown": priority,
        "stock_by_category": categories,
        "request_trend": trend,
        "critical_shortages": shortages,
    }
