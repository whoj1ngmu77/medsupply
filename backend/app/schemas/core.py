from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EMERGENCY_LEVELS = {"NORMAL", "ELEVATED", "HIGH", "CRITICAL"}
CRITICALITIES = {"ROUTINE", "ESSENTIAL", "LIFE_SAVING"}


class Page(BaseModel):
    """Envelope for paginated list responses."""
    items: list
    total: int
    limit: int
    offset: int


# ---------- Hospital ----------

class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    reg_number: str = Field(min_length=3, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    bed_capacity: int = Field(gt=0, le=10000)
    emergency_level: str = "NORMAL"
    contact_phone: str | None = Field(default=None, max_length=20)

    @field_validator("emergency_level")
    @classmethod
    def valid_level(cls, v: str) -> str:
        if v not in EMERGENCY_LEVELS:
            raise ValueError(f"must be one of {sorted(EMERGENCY_LEVELS)}")
        return v


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    bed_capacity: int | None = Field(default=None, gt=0, le=10000)
    emergency_level: str | None = None
    contact_phone: str | None = None

    @field_validator("emergency_level")
    @classmethod
    def valid_level(cls, v):
        if v is not None and v not in EMERGENCY_LEVELS:
            raise ValueError(f"must be one of {sorted(EMERGENCY_LEVELS)}")
        return v


class HospitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hospital_id: int
    name: str
    reg_number: str
    address: str | None
    city: str
    state: str | None
    bed_capacity: int
    emergency_level: str
    contact_phone: str | None


# ---------- Warehouse ----------

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str | None = None
    city: str = Field(min_length=2, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    storage_capacity: int = Field(gt=0)


class WarehouseUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    storage_capacity: int | None = Field(default=None, gt=0)


class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warehouse_id: int
    name: str
    address: str | None
    city: str
    storage_capacity: int


# ---------- Medicine ----------

class MedicineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    generic_name: str | None = Field(default=None, max_length=150)
    category_id: int
    manufacturer_id: int
    unit: str = Field(min_length=1, max_length=30)
    criticality: str = "ROUTINE"
    is_controlled: bool = False
    storage_temp: str | None = None

    @field_validator("criticality")
    @classmethod
    def valid_crit(cls, v: str) -> str:
        if v not in CRITICALITIES:
            raise ValueError(f"must be one of {sorted(CRITICALITIES)}")
        return v


class MedicineUpdate(BaseModel):
    name: str | None = None
    generic_name: str | None = None
    category_id: int | None = None
    manufacturer_id: int | None = None
    unit: str | None = None
    criticality: str | None = None
    is_controlled: bool | None = None
    storage_temp: str | None = None


class MedicineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    medicine_id: int
    name: str
    generic_name: str | None
    category_id: int
    manufacturer_id: int
    unit: str
    criticality: str
    is_controlled: bool
    storage_temp: str | None


# ---------- Supplier ----------

class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    gst_number: str = Field(min_length=15, max_length=20)
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supplier_id: int
    name: str
    gst_number: str
    contact_email: str | None
    contact_phone: str | None
    rating: float | None


# ---------- Inventory ----------

class InventoryBatchCreate(BaseModel):
    warehouse_id: int
    medicine_id: int
    batch_number: str = Field(min_length=1, max_length=60)
    qty_on_hand: int = Field(ge=0)
    mfg_date: date | None = None
    expiry_date: date
    unit_cost: float | None = Field(default=None, ge=0)


class InventoryBatchUpdate(BaseModel):
    """qty_reserved is deliberately NOT updatable here.

    Reservations are made only by the allocation transaction (Phase 6),
    which holds a row lock. Allowing a plain UPDATE would bypass the
    concurrency control entirely.
    """
    qty_on_hand: int | None = Field(default=None, ge=0)
    expiry_date: date | None = None
    unit_cost: float | None = Field(default=None, ge=0)


class InventoryBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: int
    warehouse_id: int
    medicine_id: int
    batch_number: str
    qty_on_hand: int
    qty_reserved: int
    mfg_date: date | None
    expiry_date: date
    unit_cost: float | None


class AvailableInventoryOut(BaseModel):
    """Projection of v_available_inventory."""
    batch_id: int
    warehouse_id: int
    warehouse_name: str
    medicine_id: int
    medicine_name: str
    criticality: str
    batch_number: str
    qty_on_hand: int
    qty_reserved: int
    qty_available: int
    expiry_date: date
