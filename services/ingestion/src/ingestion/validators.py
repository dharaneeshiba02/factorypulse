"""Syntactic, physical-range, and per-stream ordering validation."""

from __future__ import annotations

import logging
import math

from ingestion.config import config
from ingestion.schemas import TelemetryReading

logger = logging.getLogger(__name__)

# Conservative physical bounds for named industrial channels. Per-asset sensor
# bounds stored in the registry take precedence in BatchWriter.
SENSOR_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (-40.0, 400.0),
    "vibration": (0.0, 50.0),
    "pressure": (0.0, 500.0),
    "rpm": (0.0, 50_000.0),
    "current": (0.0, 200.0),
}


def validate_reading(reading: TelemetryReading) -> tuple[bool, str]:
    """Validate one already-parsed reading."""
    if not math.isfinite(reading.value):
        return False, "value must be finite"
    if reading.quality < config.min_quality:
        return False, f"quality {reading.quality} is below {config.min_quality}"
    if abs(reading.value) > config.max_sensor_value:
        return False, f"value exceeds configured maximum {config.max_sensor_value}"
    return True, ""


def validate_batch(
    readings: list[TelemetryReading],
) -> tuple[list[TelemetryReading], list[str]]:
    """Return valid readings and one reason for each rejected reading.

    Input order must be strictly increasing for each machine/sensor stream.
    Different machines and sensors may be interleaved in the batch.
    """
    valid: list[TelemetryReading] = []
    errors: list[str] = []
    previous: dict[tuple[str, str], object] = {}
    for reading in readings:
        ok, reason = validate_reading(reading)
        key = (reading.machine_id, reading.sensor)
        last_time = previous.get(key)
        if ok and last_time is not None and reading.time <= last_time:
            ok = False
            reason = f"timestamp is not increasing for {reading.machine_id}/{reading.sensor}"
        if ok:
            valid.append(reading)
            # A rejected out-of-order row must not move the stream cursor
            # backwards and make a later row appear valid.
            previous[key] = reading.time
        else:
            errors.append(reason)
            logger.warning("Rejected %s/%s: %s", *key, reason)
    return valid, errors
