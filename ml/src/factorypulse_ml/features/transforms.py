"""Shared sensor transforms used by batch training and live ingestion."""

from __future__ import annotations

import pandas as pd

from factorypulse_ml.features.rolling import rolling_features
from factorypulse_ml.features.spectral import spectral_features
from factorypulse_ml.features.trends import trend_features

BASE_COLUMNS = {"time", "machine_id", "sensor", "value", "quality"}
DEFAULT_HISTORY = 50


def transform_sensor_readings(
    readings: pd.DataFrame,
    *,
    rolling_windows: list[int] | None = None,
    trend_windows: list[int] | None = None,
    spectral_window: int = DEFAULT_HISTORY,
) -> pd.DataFrame:
    """Apply the canonical rolling, trend, and spectral transforms.

    ``readings`` must contain the canonical long-form telemetry columns. The
    same function is called by the offline feature pipeline and online writer.
    """
    missing = BASE_COLUMNS - set(readings.columns)
    if missing:
        raise ValueError(f"Missing canonical telemetry columns: {sorted(missing)}")
    if readings.empty:
        return readings.copy()

    result = readings.copy()
    result["time"] = pd.to_datetime(result["time"], utc=True)
    result = result.sort_values(["machine_id", "sensor", "time"])
    result = rolling_features(result, windows=rolling_windows or [5, 10, 20])
    result = trend_features(result, windows=trend_windows or [10, 20])
    result = spectral_features(result, window=spectral_window)
    return result


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Return generated numeric feature names in stable order."""
    return [
        name
        for name in frame.columns
        if name not in BASE_COLUMNS and pd.api.types.is_numeric_dtype(frame[name])
    ]
