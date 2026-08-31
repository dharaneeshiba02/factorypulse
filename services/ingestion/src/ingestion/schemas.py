"""Pydantic models for telemetry ingestion."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TelemetryReading(BaseModel):
    """A single sensor reading."""
    time: datetime
    machine_id: str
    sensor: str
    value: float
    quality: int = Field(default=100, ge=0, le=100)


class TelemetryBatch(BaseModel):
    """Batch of readings sent by the simulator or external systems."""
    readings: List[TelemetryReading]

    @field_validator("readings")
    @classmethod
    def non_empty(cls, v: List[TelemetryReading]) -> List[TelemetryReading]:
        if not v:
            raise ValueError("readings list must not be empty")
        return v


class IngestResponse(BaseModel):
    """Response returned after ingestion."""
    accepted: int = 0
    rejected: int = 0
    errors: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Service health check response."""
    status: str = "ok"
    db_connected: bool = False
    mqtt_connected: bool = False
