from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class Shipment(Base):
    __tablename__ = "shipment"

    shipment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allocation_id: Mapped[int] = mapped_column(
        ForeignKey("allocation.allocation_id"), unique=True, nullable=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(30))
    driver_name: Mapped[str | None] = mapped_column(String(150))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(20), default="PREPARING")


class SupplyConsignment(Base):
    __tablename__ = "supply_consignment"

    consignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("supplier.supplier_id"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicine.medicine_id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.warehouse_id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_batch.batch_id"), unique=True)
    qty_supplied: Mapped[int] = mapped_column(Integer, nullable=False)
    supplied_on: Mapped[date] = mapped_column(Date, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
