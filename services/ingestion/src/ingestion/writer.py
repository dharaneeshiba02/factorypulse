"""Validated asynchronous telemetry batching and TimescaleDB persistence."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import asyncpg

from ingestion.config import config
from ingestion.feature_store import FeatureStore
from ingestion.schemas import TelemetryReading
from ingestion.validators import SENSOR_RANGES, validate_batch

logger = logging.getLogger(__name__)

INSERT_TELEMETRY_SQL = """INSERT INTO telemetry (time, machine_id, sensor, value, quality)
VALUES ($1, $2, $3, $4, $5)"""


class BatchWriter:
    """Validate readings, record rejects, and batch writes to TimescaleDB."""

    def __init__(self) -> None:
        self._buffer: list[TelemetryReading] = []
        self._pool: asyncpg.Pool | None = None
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._validation_lock = asyncio.Lock()
        self._last_received: dict[tuple[str, str], datetime] = {}
        self.feature_store = FeatureStore()

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(
            config.database_url.replace("postgresql://", "postgres://"),
            min_size=2,
            max_size=10,
        )
        await self.feature_store.start()
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("BatchWriter started; database pool ready")

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush(force=True)
        await self.feature_store.close()
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def record_dead_letter(
        self, payload: Any, reason_code: str, reason_detail: str
    ) -> None:
        """Persist a malformed or rejected payload for operator review."""
        if self._pool is None:
            logger.error("Cannot persist dead letter before the database is ready")
            return
        try:
            raw_json = json.dumps(payload, default=str, allow_nan=False)
        except (TypeError, ValueError):
            raw_json = json.dumps({"unserializable_payload": repr(payload)})
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO telemetry_dead_letter
                   (raw_payload, reason_code, reason_detail)
                   VALUES ($1::jsonb, $2, $3)""",
                raw_json,
                reason_code[:64],
                reason_detail[:4000],
            )

    async def _registry_state(
        self, readings: list[TelemetryReading]
    ) -> dict[tuple[str, str], tuple[float | None, float | None, datetime | None]]:
        """Load physical limits and last stored timestamps for each stream."""
        if self._pool is None or not readings:
            return {}
        keys = list(dict.fromkeys((r.machine_id, r.sensor) for r in readings))
        machine_ids = [key[0] for key in keys]
        sensors = [key[1] for key in keys]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT requested.machine_id, requested.sensor,
                          registered.min_valid, registered.max_valid, latest.time
                   FROM unnest($1::text[], $2::text[])
                        AS requested(machine_id, sensor)
                   LEFT JOIN sensors AS registered
                     ON registered.machine_id = requested.machine_id
                    AND registered.sensor = requested.sensor
                   LEFT JOIN LATERAL (
                       SELECT time FROM telemetry AS telemetry_row
                       WHERE telemetry_row.machine_id = requested.machine_id
                         AND telemetry_row.sensor = requested.sensor
                       ORDER BY time DESC LIMIT 1
                   ) AS latest ON TRUE""",
                machine_ids,
                sensors,
            )
        return {
            (row["machine_id"], row["sensor"]): (
                row["min_valid"],
                row["max_valid"],
                row["time"],
            )
            for row in rows
        }

    async def ingest(
        self, readings: list[TelemetryReading], raw_payload: Any | None = None
    ) -> tuple[int, int, list[str]]:
        """Validate a batch, persist rejects, and queue accepted readings."""
        valid, errors = validate_batch(readings)
        rejected_readings: list[tuple[TelemetryReading, str]] = []
        if errors:
            # validate_batch preserves input order and returns one reason per
            # reject. Re-run the small validation pass to associate reasons.
            from ingestion.validators import validate_reading

            previous: dict[tuple[str, str], datetime] = {}
            for reading in readings:
                ok, reason = validate_reading(reading)
                key = (reading.machine_id, reading.sensor)
                if ok and key in previous and reading.time <= previous[key]:
                    ok, reason = False, f"timestamp is not increasing for {reading.machine_id}/{reading.sensor}"
                if ok:
                    previous[key] = reading.time
                else:
                    rejected_readings.append((reading, reason))

        async with self._validation_lock:
            state = await self._registry_state(valid)
            accepted: list[TelemetryReading] = []
            for reading in valid:
                key = (reading.machine_id, reading.sensor)
                minimum, maximum, stored_time = state.get(key, (None, None, None))
                default_bounds = SENSOR_RANGES.get(reading.sensor)
                if default_bounds is not None:
                    minimum = minimum if minimum is not None else default_bounds[0]
                    maximum = maximum if maximum is not None else default_bounds[1]
                last_time = max(
                    (value for value in (stored_time, self._last_received.get(key)) if value is not None),
                    default=None,
                )
                reason = ""
                if minimum is not None and reading.value < minimum:
                    reason = f"value {reading.value} is below registered minimum {minimum}"
                elif maximum is not None and reading.value > maximum:
                    reason = f"value {reading.value} exceeds registered maximum {maximum}"
                elif last_time is not None and reading.time <= last_time:
                    reason = f"timestamp is not newer than stored data for {reading.machine_id}/{reading.sensor}"
                if reason:
                    rejected_readings.append((reading, reason))
                    errors.append(reason)
                else:
                    accepted.append(reading)
                    self._last_received[key] = reading.time

            if rejected_readings:
                fallback_payload = raw_payload
                for reading, reason in rejected_readings:
                    await self.record_dead_letter(
                        fallback_payload
                        if fallback_payload is not None
                        else reading.model_dump(mode="json"),
                        "validation",
                        reason,
                    )
            if accepted:
                await self.enqueue(accepted)

        return len(accepted), len(rejected_readings), errors[:10]

    async def enqueue(self, readings: list[TelemetryReading]) -> None:
        async with self._lock:
            self._buffer.extend(readings)
            should_flush = len(self._buffer) >= config.batch_size
        if should_flush:
            await self._flush()

    async def ensure_registry(self, conn: Any, readings: list[TelemetryReading]) -> None:
        """Register first-seen simulator machines and sensor channels."""
        machine_ids = sorted({r.machine_id for r in readings})
        sensor_pairs = sorted({(r.machine_id, r.sensor) for r in readings})
        await conn.executemany(
            """INSERT INTO assets
               (machine_id, name, machine_class, asset_type, location)
               VALUES ($1, $1, 'unclassified', 'unclassified', 'telemetry')
               ON CONFLICT (machine_id) DO NOTHING""",
            [(machine_id,) for machine_id in machine_ids],
        )
        await conn.executemany(
            """INSERT INTO sensors (sensor_id, machine_id, sensor, unit)
               VALUES ($1, $2, $3, '')
               ON CONFLICT (machine_id, sensor) DO NOTHING""",
            [(f"{machine_id}:{sensor}", machine_id, sensor) for machine_id, sensor in sensor_pairs],
        )

    async def _flush(self, force: bool = False) -> None:
        async with self._lock:
            if not self._buffer:
                return
            count = len(self._buffer) if force else min(len(self._buffer), config.batch_size)
            batch = self._buffer[:count]
            del self._buffer[:count]

        if self._pool is None:
            async with self._lock:
                self._buffer = batch + self._buffer
            logger.error("No database pool; retained %d readings for retry", len(batch))
            return

        rows = [(r.time, r.machine_id, r.sensor, r.value, r.quality) for r in batch]
        try:
            cache_updates: list[tuple[str, str]] = []
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await self.ensure_registry(conn, batch)
                    await conn.executemany(INSERT_TELEMETRY_SQL, rows)
                    cache_updates = await self.feature_store.store_batch(conn, batch)
            await self.feature_store.update_cache(cache_updates)
            logger.info("Persisted %d telemetry readings and derived features", len(rows))
        except Exception:
            async with self._lock:
                self._buffer = batch + self._buffer
            logger.exception("Failed to persist %d readings; retained them for retry", len(rows))

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(config.flush_interval_seconds)
            await self._flush()
