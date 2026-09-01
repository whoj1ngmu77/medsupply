from datetime import datetime

from sqlalchemy import (BigInteger, DateTime, ForeignKey, Integer, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class EmergencyRequest(Base):
    __tablename__ = "emergency_request"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(
        ForeignKey("hospital.hospital_id"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicine.medicine_id"), nullable=False)
    qty_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_fulfilled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    request_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    required_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raised_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.user_id"))
    incident_id: Mapped[str | None] = mapped_column(String(24))


class Allocation(Base):
    __tablename__ = "allocation"

    allocation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("emergency_request.request_id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_batch.batch_id"), nullable=False)
    qty_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    allocated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.user_id"))
    allocation_status: Mapped[str] = mapped_column(String(20), default="RESERVED")


class AllocationEvent(Base):
    __tablename__ = "allocation_event"

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer)
    batch_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    txn_note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.user_id"))
    actor_type: Mapped[str] = mapped_column(String(20), default="USER")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
