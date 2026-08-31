"""Trend-based features — slope, rate-of-change, acceleration."""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _linear_slope(series: pd.Series) -> float:
    """Fit a linear trend and return the slope."""
    n = len(series)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = series.values.astype(float)
    mask = np.isfinite(y)
    if mask.sum() < 2:
        return 0.0
    x, y = x[mask], y[mask]
    slope = np.polyfit(x, y, 1)[0]
    return float(slope)


def trend_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compute trend features per machine+sensor group.

    Features:
    - Linear slope over each window
    - Rate of change (first difference)
    - Acceleration (second difference)
    """
    if windows is None:
        windows = [10, 20, 50]
    if group_cols is None:
        group_cols = ["machine_id", "sensor"]

    df = df.sort_values(group_cols + ["time"]).copy()
    result_frames = []

    for key, grp in df.groupby(group_cols):
        feat_df = grp.copy()
        values = grp["value"]

        # Rate of change and acceleration
        feat_df["rate_of_change"] = values.diff().fillna(0)
        feat_df["acceleration"] = values.diff().diff().fillna(0)

        # Rolling linear slope
        for w in windows:
            feat_df[f"slope_{w}"] = values.rolling(window=w, min_periods=2).apply(
                _linear_slope, raw=False
            ).fillna(0)

        result_frames.append(feat_df)

    result = pd.concat(result_frames, ignore_index=True)
    logger.info("Computed trend features — %d rows", len(result))
    return result
