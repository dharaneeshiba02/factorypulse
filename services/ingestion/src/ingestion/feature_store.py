"""Persist features and maintain the Redis online cache from canonical readings."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd
from redis.asyncio import Redis, from_url

from factorypulse_ml.features.transforms import feature_columns, transform_sensor_readings
from ingestion.config import config
from ingestion.schemas import TelemetryReading

logger = logging.getLogger(__name__)


class FeatureStore:
    """Use the shared offline transform for live features, DB writes and caching."""

    def __init__(self) -> None:
        self.redis: Redis | None = None
        self.redis_connected = False

    async def start(self) -> None:
        self.redis = from_url(config.redis_url, decode_responses=True)
        try:
            await self.redis.ping()
            self.redis_connected = True
        except Exception:
            logger.exception("Redis is unavailable; online reads will use TimescaleDB")
            self.redis_connected = False

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
            self.redis_connected = False

    @staticmethod
    def _history_key(machine_id: str, sensor: str) -> str:
        return f"factorypulse:history:{machine_id}:{sensor}"

    @staticmethod
    def _snapshot_key(machine_id: str) -> str:
        return f"factorypulse:features:{machine_id}"

    async def _load_history(
        self, conn: Any, machine_id: str, sensor: str
    ) -> list[dict[str, Any]]:
        key = self._history_key(machine_id, sensor)
        if self.redis is not None:
            try:
                cached = await self.redis.get(key)
                if cached:
                    values = json.loads(cached)
                    if isinstance(values, list):
                        self.redis_connected = True
                        return values
            except Exception:
                self.redis_connected = False
                logger.exception("Redis history read failed; loading from TimescaleDB")

        rows = await conn.fetch(
            """SELECT time, value, quality FROM telemetry
               WHERE machine_id = $1 AND sensor = $2
               ORDER BY time DESC LIMIT $3""",
            machine_id,
            sensor,
            config.feature_history_size,
        )
        return [
            {"time": row["time"].isoformat(), "value": row["value"], "quality": row["quality"]}
            for row in reversed(rows)
        ]

    async def store_batch(
        self, conn: Any, readings: list[TelemetryReading]
    ) -> list[tuple[str, str]]:
        """Compute and persist features for all readings in an incoming batch."""
        grouped: dict[tuple[str, str], list[TelemetryReading]] = defaultdict(list)
        for reading in readings:
            grouped[(reading.machine_id, reading.sensor)].append(reading)

        feature_rows: list[tuple[datetime, str, str, float, int]] = []
        snapshots: dict[str, dict[str, float]] = defaultdict(dict)
        history_updates: list[tuple[str, str]] = []
        snapshot_times: dict[str, datetime] = {}

        for (machine_id, sensor), new_readings in grouped.items():
            new_readings.sort(key=lambda item: item.time)
            history = await self._load_history(conn, machine_id, sensor)
            records = history + [
                {
                    "time": item.time.isoformat(),
                    "machine_id": machine_id,
                    "sensor": sensor,
                    "value": item.value,
                    "quality": item.quality,
                }
                for item in new_readings
            ]
            frame = pd.DataFrame.from_records(records)
            if frame.empty:
                continue
            frame["machine_id"] = machine_id
            frame["sensor"] = sensor
            frame["time"] = pd.to_datetime(frame["time"], utc=True)
            frame = frame.drop_duplicates(subset=["time"], keep="last")
            transformed = transform_sensor_readings(
                frame,
                rolling_windows=[5, 10, 20],
                trend_windows=[10, 20],
                spectral_window=config.feature_history_size,
            )
            columns = feature_columns(transformed)
            incoming_times = {item.time for item in new_readings}
            for _, row in transformed.iterrows():
                time_value = row["time"].to_pydatetime()
                if time_value not in incoming_times:
                    continue
                feature_values = {
                    column: float(row[column])
                    for column in columns
                    if pd.notna(row[column])
                }
                for name, value in feature_values.items():
                    feature_rows.append(
                        (time_value, machine_id, f"{sensor}.{name}", value, 1)
                    )
                snapshots[machine_id].update(
                    {f"{sensor}.{name}": value for name, value in feature_values.items()}
                )
                snapshot_times[machine_id] = max(
                    snapshot_times.get(machine_id, time_value), time_value
                )

            tail = transformed.tail(config.feature_history_size)[
                ["time", "value", "quality"]
            ]
            cache_value = json.dumps(
                [
                    {
                        "time": row.time.isoformat(),
                        "value": float(row.value),
                        "quality": int(row.quality),
                    }
                    for row in tail.itertuples(index=False)
                ],
                separators=(",", ":"),
            )
            history_updates.append((self._history_key(machine_id, sensor), cache_value))

        if feature_rows:
            await conn.executemany(
                """INSERT INTO features
                   (time, machine_id, feature_name, feature_value, window_minutes)
                   VALUES ($1, $2, $3, $4, $5)""",
                feature_rows,
            )

        for machine_id, values in snapshots.items():
            previous = await conn.fetchval(
                "SELECT features FROM feature_snapshots WHERE machine_id = $1",
                machine_id,
            )
            if previous:
                if isinstance(previous, str):
                    previous = json.loads(previous)
                values = {**previous, **values}
            payload = json.dumps(values, separators=(",", ":"), allow_nan=False)
            await conn.execute(
                """INSERT INTO feature_snapshots (machine_id, time, features)
                   VALUES ($1, $2, $3::jsonb)
                   ON CONFLICT (machine_id) DO UPDATE SET
                     time = EXCLUDED.time, features = EXCLUDED.features""",
                machine_id,
                snapshot_times[machine_id],
                payload,
            )
            history_updates.append(
                (
                    self._snapshot_key(machine_id),
                    json.dumps(values, separators=(",", ":"), allow_nan=False),
                )
            )

        return history_updates

    async def update_cache(self, updates: list[tuple[str, str]]) -> None:
        """Update Redis after the database transaction has committed."""
        if self.redis is None or not updates:
            return
        try:
            for key, payload in updates:
                await self.redis.setex(key, config.feature_cache_ttl_seconds, payload)
            self.redis_connected = True
        except Exception:
            self.redis_connected = False
            logger.exception("Could not update Redis feature cache; TimescaleDB is current")

    async def get_snapshot(self, machine_id: str) -> dict[str, Any] | None:
        if self.redis is not None:
            try:
                cached = await self.redis.get(self._snapshot_key(machine_id))
                if cached:
                    self.redis_connected = True
                    return json.loads(cached)
            except Exception:
                self.redis_connected = False
                logger.exception("Redis feature snapshot read failed; using database fallback")
        if self.redis is None:
            return None
        return None
