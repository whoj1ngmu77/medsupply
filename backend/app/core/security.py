"""Password hashing and JWT token handling."""
import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# passlib probes for bcrypt.__about__, removed in bcrypt 4.x.
# Harmless — hashing works; the probe just logs a traceback.
logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)

# bcrypt with an explicit cost factor. 12 rounds is the current sane default:
# high enough to make offline brute force expensive, low enough that login
# stays under ~250ms.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash. The salt is generated per-call and embedded."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison via passlib. Never compare hashes with ==."""
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        # Malformed hash in the DB (e.g. the Phase 3 placeholder)
        return False


def create_access_token(subject: str, role: str,
                        extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret,
                      algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret,
                          algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
