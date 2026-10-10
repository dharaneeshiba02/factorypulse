"""Feature engineering pipeline — orchestrates all feature extractors.

Reads the processed (split) parquet files, computes features, and writes
the featured dataset to data/featured/.

Also computes a per-machine RUL target by counting cycles remaining.
"""
import sys
import logging
from pathlib import Path

import pandas as pd
from factorypulse_ml.features.transforms import transform_sensor_readings

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
    index = ["machine_id", "time"]
    generated = [
        name
        for name in df.columns
        if name not in {*index, "sensor", "value", "quality", "rul"}
    ]
    value_columns = ["value", *generated]
    wide = df.pivot_table(
        index=index,
        columns="sensor",
        values=value_columns,
        aggfunc="first",
    ).reset_index()
    flattened = []
    for column in wide.columns:
        if not isinstance(column, tuple):
            flattened.append(str(column))
            continue
        feature, sensor = column
        if feature in index:
            flattened.append(str(feature))
        elif feature == "value":
            flattened.append(str(sensor))
        else:
            flattened.append(f"{sensor}_{feature}")
    wide.columns = flattened

    metadata_columns = [name for name in ("rul", "quality") if name in df.columns]
    metadata = (
        df.groupby(index, as_index=False)[metadata_columns].first()
        if metadata_columns
        else df[index].drop_duplicates()
    )
    return wide.merge(metadata, on=index, how="left")


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

            # Apply the same rolling, trend, and spectral transforms used by
            # online ingestion to avoid training/serving skew.
            df = transform_sensor_readings(
                df,
                rolling_windows=[5, 10, 20],
                trend_windows=[10, 20],
                spectral_window=50,
            )

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
