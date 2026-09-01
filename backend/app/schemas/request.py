from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
STATUSES = {"PENDING", "PARTIAL", "ALLOCATED", "DISPATCHED",
            "DELIVERED", "REJECTED"}


class RequestCreate(BaseModel):
    hospital_id: int
    medicine_id: int
    qty_requested: int = Field(gt=0, le=1_000_000)
    priority: str = "MEDIUM"
    required_by: datetime | None = None
    incident_id: str | None = Field(default=None, max_length=24)

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: str) -> str:
        if v not in PRIORITIES:
            raise ValueError(f"must be one of {sorted(PRIORITIES)}")
        return v


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    hospital_id: int
    medicine_id: int
    qty_requested: int
    qty_fulfilled: int
    priority: str
    request_status: str
    requested_at: datetime
    required_by: datetime | None
    incident_id: str | None


class AllocationLine(BaseModel):
    batch_id: int
    batch_number: str
    warehouse_id: int
    qty_allocated: int
    expiry_date: str


class AllocationResult(BaseModel):
    request_id: int
    qty_requested: int
    qty_allocated: int
    qty_outstanding: int
    status: str
    lines: list[AllocationLine]
    message: str


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: int
    request_id: int
    batch_id: int
    qty_allocated: int
    allocated_at: datetime
    allocation_status: str
