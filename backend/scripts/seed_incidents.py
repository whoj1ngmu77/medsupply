"""Seed MongoDB with incidents whose `details` genuinely differ by type."""
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.mongo import mongo_client, mongo_db
from app.repositories import incident_repo as repo

random.seed(302)
CITIES = ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem",
          "Vellore", "Erode", "Tirunelveli", "Thanjavur", "Hosur"]

TEMPLATES = [
    ("FLOOD", "Monsoon flooding — {city} district", "SEVERE", lambda: {
        "water_level_m": round(random.uniform(1.2, 4.5), 1),
        "evacuation_zones": random.sample(["Zone-A", "Zone-B", "Zone-C",
                                           "Zone-D"], random.randint(1, 3)),
        "people_displaced": random.randint(200, 8000),
        "shelters_opened": random.randint(2, 15),
        "roads_impassable": random.randint(3, 40),
        "rainfall_mm_24h": random.randint(80, 400),
    }),
    ("CHEMICAL_SPILL", "Industrial chemical release — {city}", "HIGH", lambda: {
        "agent": random.choice(["Chlorine", "Ammonia", "Sulphuric acid",
                                "Benzene"]),
        "quantity_litres": random.randint(200, 12000),
        "exposure_radius_m": random.randint(150, 2500),
        "decontamination_protocol": random.choice(["HAZMAT-2", "HAZMAT-3"]),
        "ppe_level": random.choice(["Level A", "Level B", "Level C"]),
        "wind_direction": random.choice(["N", "NE", "E", "SE", "S", "SW"]),
        "air_quality_index": random.randint(150, 500),
    }),
    ("MASS_CASUALTY", "Multi-vehicle collision — {city} highway", "SEVERE",
     lambda: {
        "triage_red": random.randint(3, 30),
        "triage_yellow": random.randint(5, 50),
        "triage_green": random.randint(10, 90),
        "triage_black": random.randint(0, 12),
        "vehicles_involved": random.randint(2, 20),
        "extrication_required": random.randint(0, 8),
        "trauma_centres_activated": random.randint(1, 5),
    }),
    ("DISEASE_OUTBREAK", "Suspected {city} cluster outbreak", "HIGH", lambda: {
        "pathogen": random.choice(["Dengue", "Cholera", "Influenza A/H1N1",
                                   "Leptospirosis"]),
        "confirmed_cases": random.randint(15, 900),
        "suspected_cases": random.randint(30, 2500),
        "r_naught": round(random.uniform(1.1, 3.8), 2),
        "quarantine_wards": random.randint(1, 12),
        "vaccination_drive": random.choice([True, False]),
        "case_curve": [random.randint(1, 60) for _ in range(7)],
    }),
    ("FIRE", "Structural fire — {city} commercial block", "MODERATE", lambda: {
        "structure_type": random.choice(["Residential", "Commercial",
                                         "Industrial", "Hospital"]),
        "floors_affected": random.randint(1, 12),
        "burn_victims": random.randint(0, 25),
        "smoke_inhalation_cases": random.randint(2, 60),
        "fire_tenders_deployed": random.randint(2, 18),
        "contained": random.choice([True, False]),
    }),
    ("EARTHQUAKE", "Seismic event near {city}", "CATASTROPHIC", lambda: {
        "magnitude": round(random.uniform(4.2, 7.4), 1),
        "depth_km": round(random.uniform(5, 60), 1),
        "aftershocks_recorded": random.randint(0, 45),
        "buildings_collapsed": random.randint(0, 200),
        "search_rescue_teams": random.randint(1, 25),
        "trapped_estimated": random.randint(0, 400),
    }),
]

TIMELINE_NOTES = [
    "Initial assessment completed by field team",
    "Medical supplies requested from central warehouse",
    "Additional ambulances dispatched",
    "Situation stabilising; casualty intake slowing",
    "Coordination call held with district administration",
]


async def main():
    await mongo_db["incidents"].delete_many({})
    await mongo_db["incident_updates"].delete_many({})

    idx = await repo.ensure_indexes(mongo_db)
    print(f"Indexes created: {sorted(idx.keys())}\n")

    created = 0
    for i in range(36):
        itype, title_tpl, sev, detail_fn = random.choice(TEMPLATES)
        city = random.choice(CITIES)
        doc = {
            "incident_type": itype,
            "title": title_tpl.format(city=city),
            "severity": random.choice(
                [sev, sev, "MODERATE", "HIGH", "SEVERE"]),
            "location": {"city": city, "district": f"{city} District",
                         "lat": round(random.uniform(8.0, 13.5), 4),
                         "lng": round(random.uniform(76.5, 80.5), 4)},
            "affected_hospital_ids": random.sample(range(1, 201),
                                                   random.randint(1, 6)),
            "reported_by": random.choice(["coordinator", "field_team_1",
                                          "district_admin"]),
            "details": detail_fn(),
            "tags": random.sample(
                ["urgent", "ongoing", "multi-agency", "resolved",
                 "media-attention", "resource-critical"],
                random.randint(1, 3)),
        }
        rec = await repo.create(mongo_db, doc)
        created += 1

        for _ in range(random.randint(1, 4)):
            await repo.add_timeline_entry(mongo_db, rec["id"], {
                "note": random.choice(TIMELINE_NOTES),
                "author": random.choice(["coordinator", "field_team_1"]),
                "data": {"personnel_on_site": random.randint(5, 120)},
            })

    print(f"Created {created} incidents with timelines.\n")

    s = await repo.stats(mongo_db)
    print(f"Total: {s['total']}  Active: {s['active']}")
    print("\nBy type:")
    for r in s["by_type"]:
        print(f"  {r['_id']:<18} {r['count']}")
    print("\nSCHEMA VARIATION — detail fields per incident type:")
    for r in s["detail_fields_per_type"]:
        print(f"\n  {r['_id']}:")
        print(f"    {', '.join(sorted(r['fields']))}")
    print("\nNo two incident types share the same field set. This is the "
          "architectural justification for MongoDB.")

    mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
