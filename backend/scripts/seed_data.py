"""
Seed MedSupply with deterministic data.

  python seed_data.py --mode small   ~200 rows, readable, for demos
  python seed_data.py --mode bulk    ~120k rows, for index/optimization work

Deterministic: fixed random seed, so index timings are comparable
across machines and reruns.
"""
import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import engine

SEED = 302
random.seed(SEED)

CATEGORIES = [
    ("Analgesics", "Pain relief"),
    ("Antibiotics", "Bacterial infection treatment"),
    ("Antivirals", "Viral infection treatment"),
    ("Cardiovascular", "Heart and circulation"),
    ("Endocrine", "Hormone and metabolic"),
    ("Respiratory", "Airway and lung"),
    ("Emergency", "Acute resuscitation"),
    ("Fluids", "IV fluids and electrolytes"),
]

MANUFACTURERS = [
    ("Cipla", "India"), ("Sun Pharma", "India"), ("Dr Reddys", "India"),
    ("Pfizer", "USA"), ("GSK", "UK"), ("Novartis", "Switzerland"),
    ("Serum Institute", "India"), ("Biocon", "India"),
]

MEDICINES = [
    ("Paracetamol", "Acetaminophen", 1, "tablet", "ROUTINE"),
    ("Ibuprofen", "Ibuprofen", 1, "tablet", "ROUTINE"),
    ("Morphine", "Morphine sulfate", 1, "ampoule", "LIFE_SAVING"),
    ("Amoxicillin", "Amoxicillin", 2, "capsule", "ESSENTIAL"),
    ("Azithromycin", "Azithromycin", 2, "tablet", "ESSENTIAL"),
    ("Meropenem", "Meropenem", 2, "vial", "LIFE_SAVING"),
    ("Oseltamivir", "Oseltamivir", 3, "capsule", "ESSENTIAL"),
    ("Remdesivir", "Remdesivir", 3, "vial", "LIFE_SAVING"),
    ("Atenolol", "Atenolol", 4, "tablet", "ESSENTIAL"),
    ("Adrenaline", "Epinephrine", 4, "ampoule", "LIFE_SAVING"),
    ("Heparin", "Heparin sodium", 4, "vial", "LIFE_SAVING"),
    ("Insulin", "Insulin human", 5, "vial", "LIFE_SAVING"),
    ("Levothyroxine", "Levothyroxine", 5, "tablet", "ROUTINE"),
    ("Salbutamol", "Salbutamol", 6, "inhaler", "ESSENTIAL"),
    ("Oxygen Concentrate", "Medical oxygen", 6, "cylinder", "LIFE_SAVING"),
    ("Atropine", "Atropine sulfate", 7, "ampoule", "LIFE_SAVING"),
    ("Naloxone", "Naloxone", 7, "ampoule", "LIFE_SAVING"),
    ("Tranexamic Acid", "Tranexamic acid", 7, "ampoule", "LIFE_SAVING"),
    ("Normal Saline", "Sodium chloride 0.9%", 8, "bag", "ESSENTIAL"),
    ("Ringer Lactate", "Compound sodium lactate", 8, "bag", "ESSENTIAL"),
]

CITIES = ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem",
          "Vellore", "Erode", "Tirunelveli", "Thanjavur", "Hosur"]

CERTS = ["COLD_CHAIN", "CONTROLLED_SUBSTANCE", "BIOHAZARD", "BULK_STORAGE"]


def wipe(conn):
    for t in ["allocation_event", "shipment", "allocation", "emergency_request",
              "supply_consignment", "inventory_batch", "custodian_category",
              "custodian", "warehouse_certification", "warehouse_service_area",
              "user_account", "medicine", "medicine_category", "manufacturer",
              "supplier", "warehouse", "hospital"]:
        conn.execute(text(f"TRUNCATE {t} RESTART IDENTITY CASCADE"))


def seed(mode):
    n_hosp = 8 if mode == "small" else 200
    n_wh = 4 if mode == "small" else 40
    n_sup = 5 if mode == "small" else 60
    n_batch = 60 if mode == "small" else 60000
    n_req = 40 if mode == "small" else 50000

    with engine.begin() as conn:
        wipe(conn)

        for name, desc in CATEGORIES:
            conn.execute(
                text("INSERT INTO medicine_category (name, description) "
                     "VALUES (:n, :d)"), {"n": name, "d": desc})

        for name, country in MANUFACTURERS:
            conn.execute(
                text("INSERT INTO manufacturer (name, country, license_no) "
                     "VALUES (:n, :c, :l)"),
                {"n": name, "c": country, "l": f"LIC-{random.randint(10000,99999)}"})

        for i, (nm, gen, cat, unit, crit) in enumerate(MEDICINES, start=1):
            conn.execute(
                text("INSERT INTO medicine (name, generic_name, category_id, "
                     "manufacturer_id, unit, criticality, is_controlled) "
                     "VALUES (:n, :g, :c, :m, :u, :cr, :ic)"),
                {"n": nm, "g": gen, "c": cat,
                 "m": random.randint(1, len(MANUFACTURERS)),
                 "u": unit, "cr": crit,
                 "ic": crit == "LIFE_SAVING" and random.random() < 0.3})

        for i in range(1, n_hosp + 1):
            conn.execute(
                text("INSERT INTO hospital (name, reg_number, city, state, "
                     "bed_capacity, emergency_level, contact_phone) "
                     "VALUES (:n, :r, :c, 'Tamil Nadu', :b, :e, :p)"),
                {"n": f"{random.choice(CITIES)} General Hospital {i}",
                 "r": f"TN-HOSP-{i:05d}",
                 "c": random.choice(CITIES),
                 "b": random.choice([50, 100, 250, 500, 800, 1200]),
                 "e": random.choice(["NORMAL", "NORMAL", "ELEVATED",
                                     "HIGH", "CRITICAL"]),
                 "p": f"+91{random.randint(7000000000, 9999999999)}"})

        for i in range(1, n_wh + 1):
            conn.execute(
                text("INSERT INTO warehouse (name, city, storage_capacity) "
                     "VALUES (:n, :c, :s)"),
                {"n": f"Central Medical Warehouse {i}",
                 "c": random.choice(CITIES),
                 "s": random.choice([4000000, 5000000, 6000000, 8000000])})
            for cert in random.sample(CERTS, random.randint(1, 3)):
                conn.execute(
                    text("INSERT INTO warehouse_certification "
                         "(warehouse_id, certification) VALUES (:w, :c)"),
                    {"w": i, "c": cert})
            for dist in random.sample(CITIES, random.randint(2, 4)):
                conn.execute(
                    text("INSERT INTO warehouse_service_area "
                         "(warehouse_id, district) VALUES (:w, :d) "
                         "ON CONFLICT DO NOTHING"),
                    {"w": i, "d": dist})

        for i in range(1, n_sup + 1):
            conn.execute(
                text("INSERT INTO supplier (name, gst_number, contact_email, "
                     "rating) VALUES (:n, :g, :e, :r)"),
                {"n": f"MedSupplier Pvt Ltd {i}",
                 "g": f"33AAAAA{i:04d}A1Z5",
                 "e": f"contact{i}@medsupplier.in",
                 "r": round(random.uniform(3.0, 5.0), 1)})

        conn.execute(
            text("INSERT INTO user_account (username, email, password_hash, "
                 "full_name, role) VALUES "
                 "('admin', 'admin@medsupply.in', 'PLACEHOLDER_SET_IN_PHASE_4', "
                 "'System Admin', 'ADMIN'), "
                 "('coordinator', 'coord@medsupply.in', "
                 "'PLACEHOLDER_SET_IN_PHASE_4', 'Emergency Coordinator', "
                 "'EMERGENCY_COORDINATOR')"))
        conn.execute(
            text("INSERT INTO user_account (username, email, password_hash, "
                 "full_name, role, hospital_id) VALUES "
                 "('hosp1', 'hosp1@medsupply.in', 'PLACEHOLDER_SET_IN_PHASE_4', "
                 "'Hospital Staff 1', 'HOSPITAL_STAFF', 1)"))
        conn.execute(
            text("INSERT INTO user_account (username, email, password_hash, "
                 "full_name, role, warehouse_id) VALUES "
                 "('wh1', 'wh1@medsupply.in', 'PLACEHOLDER_SET_IN_PHASE_4', "
                 "'Warehouse Staff 1', 'WAREHOUSE_STAFF', 1)"))

        today = date.today()
        rows = []
        for i in range(1, n_batch + 1):
            wh = random.randint(1, n_wh)
            med = random.randint(1, len(MEDICINES))
            mfg = today - timedelta(days=random.randint(30, 400))
            exp = mfg + timedelta(days=random.randint(180, 1000))
            on_hand = random.randint(50, 5000)
            rows.append({
                "w": wh, "m": med, "b": f"B{wh:03d}-{i:07d}",
                "q": on_hand, "r": random.randint(0, on_hand // 4),
                "mf": mfg, "ex": exp,
                "uc": round(random.uniform(5, 500), 2)})
            if len(rows) >= 5000:
                conn.execute(
                    text("INSERT INTO inventory_batch (warehouse_id, medicine_id, "
                         "batch_number, qty_on_hand, qty_reserved, mfg_date, "
                         "expiry_date, unit_cost) VALUES (:w, :m, :b, :q, :r, "
                         ":mf, :ex, :uc)"), rows)
                rows = []
        if rows:
            conn.execute(
                text("INSERT INTO inventory_batch (warehouse_id, medicine_id, "
                     "batch_number, qty_on_hand, qty_reserved, mfg_date, "
                     "expiry_date, unit_cost) VALUES (:w, :m, :b, :q, :r, "
                     ":mf, :ex, :uc)"), rows)

        rows = []
        for i in range(1, n_req + 1):
            req_at = today - timedelta(days=random.randint(0, 180))
            rows.append({
                "h": random.randint(1, n_hosp),
                "m": random.randint(1, len(MEDICINES)),
                "q": random.randint(10, 2000),
                "p": random.choices(
                    ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    weights=[20, 40, 30, 10])[0],
                "s": random.choices(
                    ["PENDING", "PARTIAL", "ALLOCATED", "DISPATCHED", "DELIVERED"],
                    weights=[25, 10, 20, 15, 30])[0],
                "ra": req_at,
                "rb": req_at + timedelta(days=random.randint(1, 14))})
            if len(rows) >= 5000:
                conn.execute(
                    text("INSERT INTO emergency_request (hospital_id, medicine_id, "
                         "qty_requested, priority, request_status, requested_at, "
                         "required_by) VALUES (:h, :m, :q, :p, :s, :ra, :rb)"), rows)
                rows = []
        if rows:
            conn.execute(
                text("INSERT INTO emergency_request (hospital_id, medicine_id, "
                     "qty_requested, priority, request_status, requested_at, "
                     "required_by) VALUES (:h, :m, :q, :p, :s, :ra, :rb)"), rows)

    print(f"Seeded mode={mode}: {n_hosp} hospitals, {n_wh} warehouses, "
          f"{n_batch} batches, {n_req} requests (seed={SEED})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["small", "bulk"], default="small")
    args = ap.parse_args()
    seed(args.mode)
