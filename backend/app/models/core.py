from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class Hospital(Base):
    __tablename__ = "hospital"

    hospital_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    reg_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    bed_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    emergency_level: Mapped[str] = mapped_column(String(20), default="NORMAL")
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class Warehouse(Base):
    __tablename__ = "warehouse"

    warehouse_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    storage_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class Manufacturer(Base):
    __tablename__ = "manufacturer"

    manufacturer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    license_no: Mapped[str | None] = mapped_column(String(60))


class MedicineCategory(Base):
    __tablename__ = "medicine_category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Medicine(Base):
    __tablename__ = "medicine"

    medicine_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(150))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("medicine_category.category_id"), nullable=False)
    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturer.manufacturer_id"), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    criticality: Mapped[str] = mapped_column(String(20), default="ROUTINE")
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_temp: Mapped[str | None] = mapped_column(String(30))


class Supplier(Base):
    __tablename__ = "supplier"

    supplier_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    gst_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(150))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1))


class InventoryBatch(Base):
    __tablename__ = "inventory_batch"

    batch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.warehouse_id"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicine.medicine_id"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(60), nullable=False)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mfg_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
