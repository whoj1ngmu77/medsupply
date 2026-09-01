from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ROLES = {"ADMIN", "HOSPITAL_STAFF", "WAREHOUSE_STAFF",
         "SUPPLIER", "EMERGENCY_COORDINATOR"}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=150)
    role: str
    hospital_id: int | None = None
    warehouse_id: int | None = None
    supplier_id: int | None = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"role must be one of {sorted(ROLES)}")
        return v

    @field_validator("username")
    @classmethod
    def alnum_username(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("username must be alphanumeric or underscore")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: str
    full_name: str | None
    role: str
    hospital_id: int | None
    warehouse_id: int | None
    supplier_id: int | None
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
