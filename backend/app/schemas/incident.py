from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

INCIDENT_TYPES = {"FLOOD", "CHEMICAL_SPILL", "MASS_CASUALTY",
                  "DISEASE_OUTBREAK", "FIRE", "EARTHQUAKE", "OTHER"}
SEVERITIES = {"LOW", "MODERATE", "HIGH", "SEVERE", "CATASTROPHIC"}


class IncidentCreate(BaseModel):
    """The `details` field is deliberately unconstrained.

    Its shape depends entirely on incident_type. That variability is
    the architectural reason MongoDB is here at all.
    """
    model_config = ConfigDict(extra="forbid")

    incident_type: str
    title: str = Field(min_length=3, max_length=200)
    severity: str = "MODERATE"
    location: dict[str, Any] = Field(
        default_factory=dict,
        description="e.g. {'city': 'Chennai', 'district': 'Adyar', "
                    "'lat': 13.0, 'lng': 80.2}")
    affected_hospital_ids: list[int] = Field(default_factory=list)
    reported_by: str | None = None
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific payload. Schema varies by incident_type.")
    tags: list[str] = Field(default_factory=list)

    @field_validator("incident_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in INCIDENT_TYPES:
            raise ValueError(f"must be one of {sorted(INCIDENT_TYPES)}")
        return v

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, v: str) -> str:
        if v not in SEVERITIES:
            raise ValueError(f"must be one of {sorted(SEVERITIES)}")
        return v


class IncidentUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    details: dict[str, Any] | None = None
    tags: list[str] | None = None


class IncidentTimelineEntry(BaseModel):
    note: str = Field(min_length=1, max_length=1000)
    author: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class IncidentOut(BaseModel):
    id: str
    incident_type: str
    title: str
    severity: str
    status: str
    location: dict[str, Any]
    affected_hospital_ids: list[int]
    reported_by: str | None
    details: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime | None = None
    timeline_count: int = 0
