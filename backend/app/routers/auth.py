from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, require_roles
from app.core.security import (create_access_token, hash_password,
                               verify_password)
from app.db.postgres import get_db
from app.models.user import UserAccount
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    stmt = select(UserAccount).where(UserAccount.username == payload.username)
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(
        subject=user.username,
        role=user.role,
        extra={"uid": user.user_id},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=UserOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles("ADMIN"))])
def register(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.execute(
        select(UserAccount).where(
            (UserAccount.username == payload.username)
            | (UserAccount.email == payload.email)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    user = UserAccount(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        hospital_id=payload.hospital_id,
        warehouse_id=payload.warehouse_id,
        supplier_id=payload.supplier_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
def me(user: UserAccount = Depends(get_current_user)):
    return user
