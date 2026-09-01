"""Live EXPLAIN ANALYZE harness for the DBMS Demonstrations page.

Only whitelisted queries can run. The keys are keys, not SQL — the client
never supplies a query string, so this endpoint cannot be used for
injection even though it executes raw SQL.
"""
import re
import statistics

from sqlalchemy import text
from sqlalchemy.orm import Session

BENCHMARKS = {
    "batch_by_warehouse_medicine": {
        "label": "Batch lookup by warehouse + medicine",
        "sql": ("SELECT * FROM inventory_batch "
                "WHERE warehouse_id = 5 AND medicine_id = 12"),
        "index": "idx_batch_wh_med",
        "endpoint": "GET /inventory?warehouse_id=5&medicine_id=12",
    },
    "expiry_range": {
        "label": "Batches expiring within 90 days",
        "sql": ("SELECT batch_id, batch_number, expiry_date "
                "FROM inventory_batch WHERE expiry_date "
                "BETWEEN CURRENT_DATE AND CURRENT_DATE + 90"),
        "index": "idx_batch_expiry",
        "endpoint": "GET /inventory/expiring",
    },
    "open_critical_requests": {
        "label": "Open CRITICAL requests (partial index)",
        "sql": ("SELECT request_id, hospital_id, qty_requested "
                "FROM emergency_request "
                "WHERE request_status IN ('PENDING','PARTIAL') "
                "AND priority = 'CRITICAL'"),
        "index": "idx_request_open",
        "endpoint": "GET /requests/queue",
    },
    "fefo_selection": {
        "label": "FEFO batch selection (allocation hot path)",
        "sql": ("SELECT batch_id, qty_on_hand - qty_reserved AS avail "
                "FROM inventory_batch WHERE medicine_id = 12 "
                "AND expiry_date > CURRENT_DATE "
                "AND (qty_on_hand - qty_reserved) > 0 "
                "ORDER BY expiry_date ASC, batch_id ASC"),
        "index": "idx_batch_fefo",
        "endpoint": "POST /requests/{id}/allocate",
    },
    "hospital_history": {
        "label": "Request history for one hospital",
        "sql": ("SELECT request_id, medicine_id, qty_requested "
                "FROM emergency_request WHERE hospital_id = 42 "
                "ORDER BY requested_at DESC LIMIT 50"),
        "index": "idx_request_hospital",
        "endpoint": "GET /requests?hospital_id=42",
    },
}


def _parse(plan_lines: list[str]) -> dict:
    text_plan = "\n".join(plan_lines)
    def grab(pattern):
        m = re.search(pattern, text_plan)
        return float(m.group(1)) if m else None

    scan = "Unknown"
    for kind in ("Index Only Scan", "Index Scan", "Bitmap Heap Scan",
                 "Seq Scan"):
        if kind in text_plan:
            scan = kind
            break

    rows_removed = 0
    for m in re.finditer(r"Rows Removed by Filter: (\d+)", text_plan):
        rows_removed += int(m.group(1))

    return {
        "scan_type": scan,
        "execution_ms": grab(r"Execution Time: ([\d.]+) ms"),
        "planning_ms": grab(r"Planning Time: ([\d.]+) ms"),
        "shared_hit": grab(r"shared hit=(\d+)"),
        "shared_read": grab(r"shared read=(\d+)"),
        "rows_removed_by_filter": rows_removed,
        "has_sort_node": "Sort  " in text_plan or "->  Sort" in text_plan,
        "plan": text_plan,
    }


def run_explain(db: Session, sql: str, runs: int = 3) -> dict:
    """Run EXPLAIN (ANALYZE, BUFFERS) `runs` times, report the median.

    Median rather than mean: a single cold-cache outlier would skew a
    mean badly, and on Docker for Mac the first run is often 5-10x slower.
    """
    results = []
    for _ in range(runs):
        rows = db.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}")).scalars().all()
        results.append(_parse(rows))

    times = [r["execution_ms"] for r in results if r["execution_ms"]]
    median = statistics.median(times) if times else None
    best = min(results, key=lambda r: abs((r["execution_ms"] or 0) - median))
    best["runs"] = runs
    best["all_times_ms"] = times
    return best


def compare_with_without_index(db: Session, key: str) -> dict:
    """Same query, planner allowed and then denied index access.

    Uses enable_indexscan/enable_bitmapscan rather than DROP INDEX:
    dropping and recreating an index on a live table takes seconds and
    would make the demo unusable. SET LOCAL reverts at transaction end.
    """
    if key not in BENCHMARKS:
        raise ValueError(f"Unknown benchmark: {key}")
    bench = BENCHMARKS[key]

    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))
    without = run_explain(db, bench["sql"])

    db.execute(text("SET LOCAL enable_indexscan = on"))
    db.execute(text("SET LOCAL enable_bitmapscan = on"))
    db.execute(text("SET LOCAL enable_indexonlyscan = on"))
    with_idx = run_explain(db, bench["sql"])

    speedup = None
    if without["execution_ms"] and with_idx["execution_ms"]:
        speedup = round(without["execution_ms"] / with_idx["execution_ms"], 2)

    return {
        "key": key,
        "label": bench["label"],
        "index_name": bench["index"],
        "used_by_endpoint": bench["endpoint"],
        "without_index": without,
        "with_index": with_idx,
        "speedup_factor": speedup,
        "note": ("Measured live with EXPLAIN (ANALYZE, BUFFERS), median of "
                 "3 runs. Index access is disabled with SET LOCAL "
                 "enable_indexscan=off rather than by dropping the index."),
    }


def list_indexes(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT i.schemaname, i.relname AS table_name,
               i.indexrelname AS index_name,
               i.idx_scan AS times_used,
               pg_size_pretty(pg_relation_size(i.indexrelid)) AS size,
               a.amname AS index_type
        FROM pg_stat_user_indexes i
        JOIN pg_class c   ON c.oid = i.indexrelid
        JOIN pg_am a      ON a.oid = c.relam
        WHERE i.schemaname = 'public'
        ORDER BY pg_relation_size(i.indexrelid) DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


def table_stats(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT relname AS table_name, n_live_tup AS row_estimate,
               seq_scan, idx_scan,
               pg_size_pretty(pg_total_relation_size(relid)) AS total_size
        FROM pg_stat_user_tables
        WHERE schemaname = 'public' AND n_live_tup > 0
        ORDER BY n_live_tup DESC
    """)).mappings().all()
    return [dict(r) for r in rows]
