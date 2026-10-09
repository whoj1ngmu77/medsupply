"""Seed the supplier catalogue and per-warehouse stock policies.

The catalogue is DERIVED from supply_consignment history — the suppliers
who have actually supplied each medicine — rather than invented.

Thresholds are calibrated against each medicine's own median holding
level per warehouse, so they reflect real stock distribution instead of
arbitrary round numbers. Criticality shifts the multiplier: life-saving
medicines are held at a higher floor.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import engine

random.seed(302)   # reproducible, same seed as seed_data.py

# min_threshold and target_level as multiples of median holding
CALIBRATION = {
    "LIFE_SAVING": (0.90, 1.40),
    "ESSENTIAL":   (0.75, 1.20),
    "STANDARD":    (0.55, 1.00),
}
DEFAULT_CALIBRATION = (0.60, 1.05)

with engine.begin() as conn:
    conn.execute(text("DELETE FROM stock_policy"))
    conn.execute(text("DELETE FROM supplier_medicine"))

    # ---------------------------------------------------------------
    # 1. Catalogue from real consignment history
    # ---------------------------------------------------------------
    n_cat = conn.execute(text("""
        INSERT INTO supplier_medicine
            (supplier_id, medicine_id, unit_price, lead_time_days,
             min_order_qty, pack_size)
        SELECT supplier_id, medicine_id,
               GREATEST(ROUND(AVG(unit_price)::numeric, 2), 0.01),
               2 + (supplier_id % 5),
               100 * (1 + (medicine_id % 4)),
               50  * (1 + (medicine_id % 3))
        FROM supply_consignment
        WHERE unit_price > 0
        GROUP BY supplier_id, medicine_id
        ON CONFLICT DO NOTHING
    """)).rowcount
    print(f"Catalogue rows from consignment history: {n_cat}")

    # Any medicine with no supplier at all gets two assigned, so no
    # policy can be orphaned.
    orphans = conn.execute(text("""
        SELECT medicine_id FROM medicine
        WHERE medicine_id NOT IN (SELECT medicine_id FROM supplier_medicine)
    """)).scalars().all()
    supplier_ids = conn.execute(
        text("SELECT supplier_id FROM supplier ORDER BY supplier_id")).scalars().all()

    for mid in orphans:
        for sid in random.sample(supplier_ids, k=min(2, len(supplier_ids))):
            conn.execute(text("""
                INSERT INTO supplier_medicine
                    (supplier_id, medicine_id, unit_price, lead_time_days,
                     min_order_qty, pack_size)
                VALUES (:s, :m, :p, :l, :q, :k)
                ON CONFLICT DO NOTHING
            """), {"s": sid, "m": mid,
                   "p": round(random.uniform(5, 250), 2),
                   "l": random.randint(2, 7),
                   "q": random.choice([100, 200, 500]),
                   "k": random.choice([50, 100])})
    if orphans:
        print(f"Assigned suppliers to {len(orphans)} uncovered medicine(s)")

    total_cat = conn.execute(
        text("SELECT COUNT(*) FROM supplier_medicine")).scalar_one()
    print(f"Total catalogue rows: {total_cat}")

    # ---------------------------------------------------------------
    # 2. Median holding per (warehouse, medicine), for calibration
    # ---------------------------------------------------------------
    rows = conn.execute(text("""
        WITH holding AS (
            SELECT b.warehouse_id, b.medicine_id,
                   SUM(b.qty_on_hand - b.qty_reserved) AS available
            FROM inventory_batch b
            WHERE b.expiry_date > CURRENT_DATE
            GROUP BY b.warehouse_id, b.medicine_id
        ),
        med_median AS (
            SELECT medicine_id,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY available)
                       AS median_available
            FROM holding GROUP BY medicine_id
        )
        SELECT w.warehouse_id, m.medicine_id, m.criticality,
               COALESCE(mm.median_available, 1000) AS median_available
        FROM warehouse w
        CROSS JOIN medicine m
        LEFT JOIN med_median mm ON mm.medicine_id = m.medicine_id
        ORDER BY w.warehouse_id, m.medicine_id
    """)).mappings().all()

    # ---------------------------------------------------------------
    # 3. Best-rated supplier per medicine becomes the preferred one
    # ---------------------------------------------------------------
    pref = dict(conn.execute(text("""
        SELECT DISTINCT ON (sm.medicine_id) sm.medicine_id, sm.supplier_id
        FROM supplier_medicine sm
        JOIN supplier s ON s.supplier_id = sm.supplier_id
        WHERE sm.is_active
        ORDER BY sm.medicine_id, s.rating DESC NULLS LAST, sm.unit_price ASC
    """)).all())

    created = 0
    for r in rows:
        lo, hi = CALIBRATION.get(r["criticality"], DEFAULT_CALIBRATION)
        median = float(r["median_available"] or 1000)
        min_threshold = max(int(median * lo), 50)
        target_level = max(int(median * hi), min_threshold + 100)

        conn.execute(text("""
            INSERT INTO stock_policy
                (warehouse_id, medicine_id, min_threshold, target_level,
                 preferred_supplier_id, auto_order_enabled)
            VALUES (:w, :m, :lo, :hi, :s, TRUE)
            ON CONFLICT (warehouse_id, medicine_id) DO NOTHING
        """), {"w": r["warehouse_id"], "m": r["medicine_id"],
               "lo": min_threshold, "hi": target_level,
               "s": pref.get(r["medicine_id"])})
        created += 1

    print(f"Stock policies created: {created}")

    # ---------------------------------------------------------------
    # 4. How many are already below threshold? (nothing is ordered yet)
    # ---------------------------------------------------------------
    below = conn.execute(text("""
        WITH holding AS (
            SELECT warehouse_id, medicine_id,
                   SUM(qty_on_hand - qty_reserved) AS available
            FROM inventory_batch
            WHERE expiry_date > CURRENT_DATE
            GROUP BY warehouse_id, medicine_id
        )
        SELECT COUNT(*) FROM stock_policy p
        LEFT JOIN holding h ON h.warehouse_id = p.warehouse_id
                           AND h.medicine_id  = p.medicine_id
        WHERE COALESCE(h.available, 0) <= p.min_threshold
          AND p.auto_order_enabled
    """)).scalar_one()
    print(f"\nPolicies currently AT OR BELOW threshold: {below} / {created}")
    print("These are what the first automatic scan will act on.")
