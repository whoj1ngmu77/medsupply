"""Query optimization demonstrations — paired rewrites, live plans."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dbms.indexing import run_explain

DEMOS = {
    "selection_pushdown": {
        "title": "Selection Pushdown",
        "concept": ("Applying a filter before a join instead of after "
                    "reduces the number of tuples entering the join."),
        "variant_a": {
            "label": "Filter after join (subquery)",
            "sql": ("SELECT * FROM (SELECT b.batch_id, b.qty_on_hand, "
                    "m.name, m.criticality FROM inventory_batch b "
                    "JOIN medicine m ON m.medicine_id = b.medicine_id) sub "
                    "WHERE sub.criticality = 'LIFE_SAVING'"),
        },
        "variant_b": {
            "label": "Filter before join",
            "sql": ("SELECT b.batch_id, b.qty_on_hand, m.name, m.criticality "
                    "FROM medicine m JOIN inventory_batch b "
                    "ON b.medicine_id = m.medicine_id "
                    "WHERE m.criticality = 'LIFE_SAVING'"),
        },
        "expected": ("Plans are usually IDENTICAL. PostgreSQL's optimizer "
                     "performs selection pushdown automatically during query "
                     "rewriting. This proves the transformation is an "
                     "optimizer rule, not a programmer responsibility."),
    },
    "projection_pushdown": {
        "title": "Projection Pushdown",
        "concept": ("Selecting fewer columns can enable an index-only scan, "
                    "avoiding heap access entirely."),
        "variant_a": {
            "label": "SELECT *",
            "sql": "SELECT * FROM inventory_batch WHERE medicine_id = 12",
        },
        "variant_b": {
            "label": "Only indexed columns",
            "sql": ("SELECT medicine_id, expiry_date, batch_id "
                    "FROM inventory_batch WHERE medicine_id = 12"),
        },
        "expected": ("Variant B can use an Index Only Scan on idx_batch_fefo "
                     "because every column it needs is in the index. "
                     "Variant A must visit the heap for the other columns."),
    },
    "index_vs_seqscan": {
        "title": "Index Scan vs Sequential Scan",
        "concept": ("Selectivity decides. A seq scan is faster when a large "
                    "fraction of rows match."),
        "variant_a": {
            "label": "Highly selective (72 of 60,000 rows)",
            "sql": ("SELECT * FROM inventory_batch "
                    "WHERE warehouse_id = 5 AND medicine_id = 12"),
        },
        "variant_b": {
            "label": "Unselective (nearly all rows)",
            "sql": "SELECT * FROM inventory_batch WHERE qty_on_hand > 0",
        },
        "expected": ("A uses an index. B uses a Seq Scan and is RIGHT to: "
                     "random index lookups plus heap fetches for ~all rows "
                     "cost more than one sequential pass."),
    },
    "join_ordering": {
        "title": "Join Ordering",
        "concept": ("The optimizer reorders joins to keep intermediate "
                    "results small. join_collapse_limit=1 forces the "
                    "written order."),
        "variant_a": {
            "label": "Planner chooses the order",
            "sql": ("SELECT h.name, COUNT(*) FROM emergency_request r "
                    "JOIN hospital h ON h.hospital_id = r.hospital_id "
                    "JOIN medicine m ON m.medicine_id = r.medicine_id "
                    "WHERE m.criticality = 'LIFE_SAVING' "
                    "AND r.priority = 'CRITICAL' GROUP BY h.name"),
        },
        "variant_b": {
            "label": "Order forced as written",
            "sql": ("SELECT h.name, COUNT(*) FROM emergency_request r "
                    "JOIN hospital h ON h.hospital_id = r.hospital_id "
                    "JOIN medicine m ON m.medicine_id = r.medicine_id "
                    "WHERE m.criticality = 'LIFE_SAVING' "
                    "AND r.priority = 'CRITICAL' GROUP BY h.name"),
            "pre_sql": "SET LOCAL join_collapse_limit = 1",
        },
        "expected": ("Compare join methods (Hash vs Nested Loop) and the "
                     "order tables are joined in."),
    },
}


def run_demo(db: Session, key: str) -> dict:
    if key not in DEMOS:
        raise ValueError(f"Unknown demo: {key}")
    demo = DEMOS[key]

    results = {}
    for variant in ("variant_a", "variant_b"):
        v = demo[variant]
        if v.get("pre_sql"):
            db.execute(text(v["pre_sql"]))
        results[variant] = {"label": v["label"],
                            "sql": v["sql"],
                            **run_explain(db, v["sql"])}

    a, b = results["variant_a"], results["variant_b"]
    identical = a["scan_type"] == b["scan_type"]

    return {
        "key": key,
        "title": demo["title"],
        "concept": demo["concept"],
        "expected": demo["expected"],
        "results": results,
        "plans_use_same_scan_type": identical,
        "observation": (
            "Both variants produced the same scan type — the optimizer "
            "normalised them." if identical else
            f"Different plans: {a['scan_type']} vs {b['scan_type']}."),
    }


def list_demos() -> list[dict]:
    return [{"key": k, "title": v["title"], "concept": v["concept"]}
            for k, v in DEMOS.items()]
