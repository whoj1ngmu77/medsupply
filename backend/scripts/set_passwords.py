"""Replace the Phase 3 placeholder hashes with real bcrypt hashes.

Dev credentials only. Never use these values in a deployed system.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.security import hash_password
from app.db.postgres import engine

DEV_PASSWORDS = {
    "admin": "admin@12345",
    "coordinator": "coord@12345",
    "hosp1": "hosp1@12345",
    "wh1": "wh1@12345",
}

with engine.begin() as conn:
    for username, plain in DEV_PASSWORDS.items():
        result = conn.execute(
            text("UPDATE user_account SET password_hash = :h "
                 "WHERE username = :u"),
            {"h": hash_password(plain), "u": username},
        )
        print(f"{username}: {'updated' if result.rowcount else 'NOT FOUND'}")

print("\nDev credentials:")
for u, p in DEV_PASSWORDS.items():
    print(f"  {u} / {p}")
