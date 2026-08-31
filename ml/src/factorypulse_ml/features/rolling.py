"""Rolling window statistical features for sensor time-series."""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

DEFAULT_WINDOWS = [5, 10, 20, 50]


def rolling_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compute rolling statistics (mean, std, min, max, range) per machine+sensor.

    Parameters
    ----------
    df : DataFrame with columns [time, machine_id, sensor, value, quality]
    windows : list of window sizes (in number of readings)
    group_cols : columns to group by before computing rolling stats

    Returns
    -------
    DataFrame with original columns + new rolling feature columns.
    """
    if windows is None:
        windows = DEFAULT_WINDOWS
    if group_cols is None:
        group_cols = ["machine_id", "sensor"]

    df = df.sort_values(group_cols + ["time"]).copy()
    result_frames = []

    for key, grp in df.groupby(group_cols):
        values = grp["value"]
        feat_df = grp.copy()

        for w in windows:
            roll = values.rolling(window=w, min_periods=1)
            feat_df[f"roll_mean_{w}"] = roll.mean()
            feat_df[f"roll_std_{w}"] = roll.std().fillna(0)
            feat_df[f"roll_min_{w}"] = roll.min()
            feat_df[f"roll_max_{w}"] = roll.max()
            feat_df[f"roll_range_{w}"] = feat_df[f"roll_max_{w}"] - feat_df[f"roll_min_{w}"]

        # Exponential weighted moving average
        feat_df["ewma_10"] = values.ewm(span=10, min_periods=1).mean()
        feat_df["ewma_50"] = values.ewm(span=50, min_periods=1).mean()

        result_frames.append(feat_df)

    result = pd.concat(result_frames, ignore_index=True)
    logger.info("Computed rolling features with windows %s — %d rows", windows, len(result))
    return result
