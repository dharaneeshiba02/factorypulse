"""Training script for LightGBM failure mode classifier."""
import os
import argparse
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import mlflow

from factorypulse_ml.models.failure_lgbm import FailureClassifierLGBM
from factorypulse_ml.training.registry import register_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_failure_labels(df: pd.DataFrame, rul_threshold: int = 15) -> pd.Series:
    """
    Create synthetic failure modes based on sensor patterns near failure.
    In a real dataset, this would be provided. For C-MAPSS, we synthesize it.
    0 = Normal
    1 = Mode 1 (e.g., HPC degradation)
    2 = Mode 2 (e.g., Fan degradation)
    """
    labels = np.zeros(len(df), dtype=int)
    
    # Only label as failure if RUL is below threshold
    failure_mask = df["rul"] <= rul_threshold
    
    # Synthesize modes based on a few key sensors (e.g., sensor_11, sensor_14)
    # This is purely illustrative for the pipeline
    if "sensor_11" in df.columns and "sensor_14" in df.columns:
        mode_1_mask = failure_mask & (df["sensor_11"] > df["sensor_11"].mean())
        mode_2_mask = failure_mask & ~mode_1_mask
        
        labels[mode_1_mask] = 1
        labels[mode_2_mask] = 2
    else:
        labels[failure_mask] = 1
        
    return pd.Series(labels, index=df.index)


def main(data_dir: str):
    data_path = Path(data_dir)
    train_file = data_path / "cmapss_featured_train.parquet"
    val_file = data_path / "cmapss_featured_val.parquet"
    
    if not train_file.exists() or not val_file.exists():
        logger.error(f"Data files not found in {data_dir}")
        return
        
    train_df = pd.read_parquet(train_file).fillna(0)
    val_df = pd.read_parquet(val_file).fillna(0)
    
    if "rul" not in train_df.columns:
        logger.error("Target column 'rul' not found in dataset")
        return
        
    # Create failure mode labels
    y_train = create_failure_labels(train_df)
    y_val = create_failure_labels(val_df)
    
    exclude_cols = ["machine_id", "time", "rul"]
    features = [c for c in train_df.columns if c not in exclude_cols]
    
    X_train = train_df[features]
    X_val = val_df[features]
    
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("factorypulse_failure")
    
    with mlflow.start_run(run_name="lgbm_failure"):
        model = FailureClassifierLGBM()
        model.fit(X_train, y_train)
        
        metrics = model.evaluate(X_val, y_val)
        logger.info(f"LightGBM Validation Metrics: {metrics}")
        mlflow.log_metrics(metrics)
        
        importance_df = model.get_feature_importance()
        importance_df.to_csv("lgbm_importance.csv", index=False)
        mlflow.log_artifact("lgbm_importance.csv")
        
        mlflow.lightgbm.log_model(model.model, "model")
        register_model(mlflow.active_run().info.run_id, "factorypulse_failure_lgbm")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", help="Directory containing featured parquet files")
    args = parser.parse_args()
    main(args.data_dir)
