"""Request and response schemas for telemetry and asset registry APIs."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TelemetryReading(BaseModel):
    """Canonical single telemetry observation."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    time: datetime
    machine_id: str = Field(min_length=1, max_length=100)
    sensor: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    value: float
    quality: int = Field(default=100, ge=0, le=100)

    @field_validator("machine_id", "sensor")
    @classmethod
    def strip_identifiers(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier must not be blank")
        return value

    @field_validator("time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("time must include a timezone")
        return value


class TelemetryBatch(BaseModel):
    """A non-empty batch of canonical readings."""

    model_config = ConfigDict(extra="forbid")
    readings: list[TelemetryReading] = Field(min_length=1, max_length=10_000)


class IngestResponse(BaseModel):
    accepted: int = 0
    rejected: int = 0
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    db_connected: bool = False
    redis_connected: bool = False
    mqtt_connected: bool = False


class AssetCreate(BaseModel):
    machine_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    machine_class: str = Field(default="unclassified", min_length=1, max_length=100)
    location: str = Field(default="plant-1", max_length=200)
    install_date: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SensorCreate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    sensor: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    unit: str = Field(default="", max_length=32)
    min_valid: float | None = None
    max_valid: float | None = None

    @field_validator("max_valid")
    @classmethod
    def validate_bounds(cls, value: float | None, info):
        minimum = info.data.get("min_valid")
        if value is not None and minimum is not None and minimum > value:
            raise ValueError("min_valid must not exceed max_valid")
        return value


class MachineClassCreate(BaseModel):
    machine_class: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
