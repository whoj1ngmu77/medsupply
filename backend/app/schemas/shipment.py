from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

DELIVERY_STATUSES = {"PREPARING", "IN_TRANSIT", "DELIVERED", "FAILED"}


class ShipmentCreate(BaseModel):
    allocation_id: int
    vehicle_number: str | None = Field(default=None, max_length=30)
    driver_name: str | None = Field(default=None, max_length=150)
    expected_at: datetime | None = None


class ShipmentUpdate(BaseModel):
    vehicle_number: str | None = None
    driver_name: str | None = None
    expected_at: datetime | None = None


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_id: int
    allocation_id: int
    vehicle_number: str | None
    driver_name: str | None
    dispatched_at: datetime | None
    expected_at: datetime | None
    delivered_at: datetime | None
    delivery_status: str


class ConsignmentCreate(BaseModel):
    """Receiving stock. Creates an inventory batch as a side effect."""
    supplier_id: int
    medicine_id: int
    warehouse_id: int
    batch_number: str = Field(min_length=1, max_length=60)
    qty_supplied: int = Field(gt=0, le=1_000_000)
    mfg_date: date | None = None
    expiry_date: date
    unit_price: float | None = Field(default=None, ge=0)
    supplied_on: date | None = None


class ConsignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consignment_id: int
    supplier_id: int
    medicine_id: int
    warehouse_id: int
    batch_id: int | None
    qty_supplied: int
    supplied_on: date
    unit_price: float | None
