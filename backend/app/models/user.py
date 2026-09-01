from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey,
                        Integer, String, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class UserAccount(Base):
    __tablename__ = "user_account"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30), nullable=False)

    hospital_id: Mapped[int | None] = mapped_column(
        ForeignKey("hospital.hospital_id"))
    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse.warehouse_id"))
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier.supplier_id"))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
