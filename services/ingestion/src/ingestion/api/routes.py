"""HTTP telemetry ingestion and asset registry endpoints."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ingestion.schemas import (
    AssetCreate,
    HealthResponse,
    IngestResponse,
    MachineClassCreate,
    SensorCreate,
    TelemetryBatch,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ingestion", "asset-registry"])
_writer = None
_mqtt_consumer = None


def set_writer(writer: Any) -> None:
    global _writer
    _writer = writer


def set_mqtt_consumer(consumer: Any) -> None:
    global _mqtt_consumer
    _mqtt_consumer = consumer


def _pool():
    if _writer is None or _writer._pool is None:
        raise HTTPException(status_code=503, detail="Database is not ready")
    return _writer._pool


@router.post("/telemetry", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry(batch: TelemetryBatch) -> IngestResponse:
    """Accept a valid batch over HTTP and dead-letter rejected readings."""
    if _writer is None:
        raise HTTPException(status_code=503, detail="Writer is not initialized")
    accepted, rejected, errors = await _writer.ingest(
        batch.readings, raw_payload=batch.model_dump(mode="json")
    )
    return IngestResponse(accepted=accepted, rejected=rejected, errors=errors)


@router.get("/machine-classes")
async def list_machine_classes() -> list[dict[str, Any]]:
    async with _pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT machine_class, description FROM machine_classes ORDER BY machine_class"
        )
    return [dict(row) for row in rows]


@router.post("/machine-classes", status_code=status.HTTP_201_CREATED)
async def create_machine_class(item: MachineClassCreate) -> dict[str, str]:
    async with _pool().acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO machine_classes (machine_class, description)
               VALUES ($1, $2)
               ON CONFLICT (machine_class) DO UPDATE
                 SET description = EXCLUDED.description
               RETURNING machine_class, description""",
            item.machine_class,
            item.description,
        )
    return dict(row)


@router.get("/assets")
async def list_assets() -> list[dict[str, Any]]:
    async with _pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT machine_id, name, machine_class, location, install_date, metadata
               FROM assets ORDER BY machine_id"""
        )
    return [dict(row) for row in rows]


@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def create_asset(item: AssetCreate) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM machine_classes WHERE machine_class = $1", item.machine_class
        )
        if not exists:
            raise HTTPException(status_code=422, detail="Unknown machine_class")
        row = await conn.fetchrow(
            """INSERT INTO assets
               (machine_id, name, machine_class, asset_type, location, install_date, metadata)
               VALUES ($1, $2, $3, $3, $4, COALESCE($5, CURRENT_DATE), $6::jsonb)
               ON CONFLICT (machine_id) DO UPDATE SET
                 name = EXCLUDED.name,
                 machine_class = EXCLUDED.machine_class,
                 asset_type = EXCLUDED.asset_type,
                 location = EXCLUDED.location,
                 install_date = EXCLUDED.install_date,
                 metadata = EXCLUDED.metadata,
                 updated_at = NOW()
               RETURNING machine_id, name, machine_class, location, install_date, metadata""",
            item.machine_id,
            item.name,
            item.machine_class,
            item.location,
            item.install_date,
            json.dumps(item.metadata),
        )
    return dict(row)


@router.get("/assets/{machine_id}")
async def get_asset(machine_id: str) -> dict[str, Any]:
    async with _pool().acquire() as conn:
        row = await conn.fetchrow(
            """SELECT machine_id, name, machine_class, location, install_date, metadata
               FROM assets WHERE machine_id = $1""",
            machine_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)


@router.get("/assets/{machine_id}/sensors")
async def list_sensors(machine_id: str) -> list[dict[str, Any]]:
    async with _pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT sensor_id, machine_id, sensor, unit, min_valid, max_valid
               FROM sensors WHERE machine_id = $1 ORDER BY sensor""",
            machine_id,
        )
    return [dict(row) for row in rows]


@router.post("/assets/{machine_id}/sensors", status_code=status.HTTP_201_CREATED)
async def create_sensor(machine_id: str, item: SensorCreate) -> dict[str, Any]:
    async with _pool().acquire() as conn:
        if not await conn.fetchval("SELECT 1 FROM assets WHERE machine_id = $1", machine_id):
            raise HTTPException(status_code=404, detail="Asset not found")
        row = await conn.fetchrow(
            """INSERT INTO sensors
               (sensor_id, machine_id, sensor, unit, min_valid, max_valid)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (machine_id, sensor) DO UPDATE SET
                 unit = EXCLUDED.unit,
                 min_valid = EXCLUDED.min_valid,
                 max_valid = EXCLUDED.max_valid
               RETURNING sensor_id, machine_id, sensor, unit, min_valid, max_valid""",
            f"{machine_id}:{item.sensor}",
            machine_id,
            item.sensor,
            item.unit,
            item.min_valid,
            item.max_valid,
        )
    return dict(row)


@router.get("/features/{machine_id}")
async def get_feature_snapshot(machine_id: str) -> dict[str, Any]:
    _pool()
    snapshot = await _writer.feature_store.get_snapshot(machine_id)
    if snapshot is not None:
        return {"machine_id": machine_id, "source": "redis", "features": snapshot}
    async with _pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT time, features FROM feature_snapshots WHERE machine_id = $1",
            machine_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Feature snapshot not found")
    return {
        "machine_id": machine_id,
        "time": row["time"],
        "source": "timescaledb",
        "features": row["features"],
    }


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = False
    if _writer is not None and _writer._pool is not None:
        try:
            async with _writer._pool.acquire() as conn:
                db_ok = await conn.fetchval("SELECT 1") == 1
        except Exception:
            logger.exception("Database health check failed")
    redis_ok = bool(_writer and _writer.feature_store.redis_connected)
    mqtt_ok = bool(_mqtt_consumer and _mqtt_consumer.connected)
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_connected=db_ok,
        redis_connected=redis_ok,
        mqtt_connected=mqtt_ok,
    )


@router.get("/ready")
async def readiness() -> dict[str, str]:
    result = await health()
    if not result.db_connected:
        raise HTTPException(status_code=503, detail="Database is not ready")
    return {"status": "ready"}
