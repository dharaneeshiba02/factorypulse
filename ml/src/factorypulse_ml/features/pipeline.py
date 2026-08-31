"""Feature engineering pipeline — orchestrates all feature extractors.

Reads the processed (split) parquet files, computes features, and writes
the featured dataset to data/featured/.

Also computes a per-machine RUL target by counting cycles remaining.
"""
import sys
import logging
from pathlib import Path

import pandas as pd
import numpy as np

from factorypulse_ml.features.rolling import rolling_features
from factorypulse_ml.features.trends import trend_features
from factorypulse_ml.features.spectral import spectral_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _add_rul_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each machine, compute Remaining Useful Life as (max_cycle - current_cycle).

    The canonical data is in long format (one row per sensor per cycle), so we
    first need to infer cycles.  We use the time column to assign a cycle index
    per machine.
    """
    df = df.sort_values(["machine_id", "time"]).copy()

    # Assign cycle number = ordinal rank of the unique timestamp within a machine
    df["_ts_rank"] = df.groupby("machine_id")["time"].rank(method="dense").astype(int)
    max_rank = df.groupby("machine_id")["_ts_rank"].transform("max")
    df["rul"] = max_rank - df["_ts_rank"]
    df.drop(columns=["_ts_rank"], inplace=True)
    return df


def _pivot_sensors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot from long format (machine, sensor, value) to wide format
    (machine, sensor_1, sensor_2, ...) per time step.

    This is necessary for models that expect a feature vector per time-step.
    """
    # We need a unique row key: machine_id + time
    # Keep one row per (machine_id, time), with sensor values as columns
    id_cols = [c for c in df.columns if c not in ("sensor", "value")]
    pivot = df.pivot_table(
        index=["machine_id", "time"],
        columns="sensor",
        values="value",
        aggfunc="first",
    ).reset_index()

    # Flatten multi-level column names
    pivot.columns = [
        col if isinstance(col, str) else f"{col[0]}_{col[1]}" if col[1] else col[0]
        for col in pivot.columns
    ]

    # Merge back the non-sensor columns (rul, quality, etc.)
    meta = df.drop(columns=["sensor", "value"]).drop_duplicates(subset=["machine_id", "time"])
    result = pivot.merge(meta, on=["machine_id", "time"], how="left")
    return result


def run_feature_pipeline(processed_dir: str, featured_dir: str):
    """Main entry point for the feature pipeline."""
    processed_path = Path(processed_dir)
    featured_path = Path(featured_dir)
    featured_path.mkdir(parents=True, exist_ok=True)

    splits = ["train", "val", "test"]

    for split in splits:
        files = list(processed_path.glob(f"*_{split}.parquet"))
        if not files:
            logger.warning("No %s parquet files found in %s", split, processed_dir)
            continue

        for f in files:
            logger.info("Processing %s ...", f.name)
            df = pd.read_parquet(f)

            if df.empty:
                logger.warning("Empty file %s — writing empty output.", f.name)
                df.to_parquet(featured_path / f.name.replace(split, f"featured_{split}"), index=False)
                continue

            # 1. Add RUL target
            df = _add_rul_target(df)

            # 2. Compute rolling features (in long format)
            df = rolling_features(df, windows=[5, 10, 20])

            # 3. Compute trend features
            df = trend_features(df, windows=[10, 20])

            # Note: spectral features are expensive on large data,
            # so we skip them for the full pipeline but they're available
            # for targeted analysis.

            # 4. Pivot to wide format (one row per machine+timestep)
            df_wide = _pivot_sensors(df)

            # 5. Fill NaN from rolling windows
            df_wide = df_wide.fillna(0)

            dataset_name = f.stem.replace(f"_{split}", "")
            out_name = f"{dataset_name}_featured_{split}.parquet"
            df_wide.to_parquet(featured_path / out_name, index=False)
            logger.info("Wrote %s — %d rows, %d columns", out_name, len(df_wide), len(df_wide.columns))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pipeline.py <processed_dir> <featured_dir>")
        sys.exit(1)
    run_feature_pipeline(sys.argv[1], sys.argv[2])
