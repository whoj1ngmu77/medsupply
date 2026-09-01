"""Reusable FastAPI dependencies: DB session, current user, role guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models.user import UserAccount

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    if creds is None:
        raise CREDENTIALS_ERROR

    payload = decode_access_token(creds.credentials)
    if payload is None or "sub" not in payload:
        raise CREDENTIALS_ERROR

    stmt = select(UserAccount).where(UserAccount.username == payload["sub"])
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    return user


def require_roles(*allowed: str):
    """Route guard. Usage:

        @router.post("/", dependencies=[Depends(require_roles("ADMIN"))])
    """
    def checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation",
            )
        return user
    return checker
