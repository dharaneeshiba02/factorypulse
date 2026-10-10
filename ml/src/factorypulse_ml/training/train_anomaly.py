"""Training script for LSTM Autoencoder (Anomaly Detection)."""
import os
import argparse
import logging
from pathlib import Path
import pandas as pd
import mlflow
import torch

from factorypulse_ml.models.lstm_autoencoder import AnomalyDetector, create_sequences
from factorypulse_ml.training.registry import register_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main(data_dir: str):
    data_path = Path(data_dir)
    train_file = data_path / "cmapss_featured_train.parquet"
    val_file = data_path / "cmapss_featured_val.parquet"
    
    if not train_file.exists() or not val_file.exists():
        logger.error(f"Data files not found in {data_dir}")
        return
        
    train_df = pd.read_parquet(train_file)
    val_df = pd.read_parquet(val_file)
    
    # Fill NaNs
    train_df = train_df.fillna(0)
    val_df = val_df.fillna(0)
    
    # For anomaly detection, we train only on "normal" data
    # In C-MAPSS, early cycles are considered normal. Let's take the first 20% of cycles for each machine
    train_df["_ts_rank"] = train_df.groupby("machine_id")["time"].rank(method="dense").astype(int)
    max_rank = train_df.groupby("machine_id")["_ts_rank"].transform("max")
    normal_train_df = train_df[train_df["_ts_rank"] <= (max_rank * 0.2)]
    
    exclude_cols = ["machine_id", "time", "rul", "_ts_rank"]
    features = [c for c in normal_train_df.columns if c not in exclude_cols]
    
    seq_length = 30
    X_train = create_sequences(normal_train_df, features, seq_length)
    
    if len(X_train) == 0:
        logger.warning("Not enough data to create sequences")
        return
        
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("factorypulse_anomaly")
    
    with mlflow.start_run(run_name="lstm_autoencoder"):
        mlflow.log_param("seq_length", seq_length)
        
        model = AnomalyDetector(n_features=len(features), seq_length=seq_length, device=device)
        model.fit(X_train, epochs=20)
        
        mlflow.log_metric("anomaly_threshold", model.threshold)
        
        # Test on validation set (which contains both normal and anomalous data if we look at later cycles)
        X_val = create_sequences(val_df, features, seq_length)
        if len(X_val) > 0:
            val_scores = model.predict_score(X_val)
            mlflow.log_metric("val_mean_score", float(val_scores.mean()))
            mlflow.log_metric("val_max_score", float(val_scores.max()))
            
        mlflow.pytorch.log_model(model.model, "model")
        # Log the threshold as an artifact or tag so it can be loaded later
        mlflow.set_tag("threshold", str(model.threshold))
        
        register_model(mlflow.active_run().info.run_id, "factorypulse_anomaly_lstm")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", help="Directory containing featured parquet files")
    args = parser.parse_args()
    main(args.data_dir)
