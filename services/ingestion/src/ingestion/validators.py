"""Telemetry reading validators — range checks, nulls, quality gating."""
import logging
import math
from typing import List, Tuple
from ingestion.schemas import TelemetryReading
from ingestion.config import config

logger = logging.getLogger(__name__)

# Known sensor ranges (sensor_name -> (min, max))
SENSOR_RANGES = {
    f"sensor_{i}": (-config.max_sensor_value, config.max_sensor_value)
    for i in range(1, 22)
}


def validate_reading(reading: TelemetryReading) -> Tuple[bool, str]:
    """Validate a single reading. Returns (is_valid, error_message)."""

    # Check for NaN / Inf values
    if math.isnan(reading.value) or math.isinf(reading.value):
        return False, f"Invalid value (NaN/Inf) for {reading.machine_id}/{reading.sensor}"

    # Check quality threshold
    if reading.quality < config.min_quality:
        return False, f"Quality {reading.quality} below threshold for {reading.machine_id}/{reading.sensor}"

    # Check sensor range if known
    if reading.sensor in SENSOR_RANGES:
        lo, hi = SENSOR_RANGES[reading.sensor]
        if not (lo <= reading.value <= hi):
            return False, f"Value {reading.value} out of range [{lo}, {hi}] for {reading.sensor}"

    # Check machine_id is non-empty
    if not reading.machine_id.strip():
        return False, "Empty machine_id"

    return True, ""


def validate_batch(readings: List[TelemetryReading]) -> Tuple[List[TelemetryReading], List[str]]:
    """Validate a batch. Returns (valid_readings, error_messages)."""
    valid = []
    errors = []
    for r in readings:
        ok, err = validate_reading(r)
        if ok:
            valid.append(r)
        else:
            errors.append(err)
            logger.warning(err)
    return valid, errors
