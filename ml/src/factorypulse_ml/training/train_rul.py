"""Training script for Remaining Useful Life (RUL) models (XGBoost + Transformer)."""
import os
import argparse
import logging
from pathlib import Path
import pandas as pd
import mlflow
import torch

from factorypulse_ml.models.rul_xgboost import RULXGBoost
from factorypulse_ml.models.rul_transformer import TransformerRULModel, create_sequences_and_targets
from factorypulse_ml.training.registry import register_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def train_xgboost(train_df: pd.DataFrame, val_df: pd.DataFrame, target_col: str = "rul"):
    """Train and evaluate the XGBoost RUL model."""
    logger.info("Training XGBoost RUL Model")
    
    # Exclude non-feature columns
    exclude_cols = ["machine_id", "time", target_col]
    features = [c for c in train_df.columns if c not in exclude_cols]
    
    X_train, y_train = train_df[features], train_df[target_col]
    X_val, y_val = val_df[features], val_df[target_col]
    
    with mlflow.start_run(run_name="xgboost_rul"):
        model = RULXGBoost()
        model.fit(X_train, y_train)
        
        metrics = model.evaluate(X_val, y_val)
        logger.info(f"XGBoost Validation Metrics: {metrics}")
        mlflow.log_metrics(metrics)
        
        # Log feature importance
        importance_df = model.get_feature_importance()
        importance_df.to_csv("xgb_importance.csv", index=False)
        mlflow.log_artifact("xgb_importance.csv")
        
        mlflow.xgboost.log_model(model.model, "model")
        register_model(mlflow.active_run().info.run_id, "factorypulse_rul_xgboost")


def train_transformer(train_df: pd.DataFrame, val_df: pd.DataFrame, target_col: str = "rul"):
    """Train and evaluate the Transformer RUL model."""
    logger.info("Training Transformer RUL Model")
    
    exclude_cols = ["machine_id", "time", target_col]
    features = [c for c in train_df.columns if c not in exclude_cols]
    
    # Create sequences
    seq_length = 30
    X_train, y_train = create_sequences_and_targets(train_df, features, target_col, seq_length)
    X_val, y_val = create_sequences_and_targets(val_df, features, target_col, seq_length)
    
    if len(X_train) == 0:
        logger.warning("Not enough data to create sequences for Transformer")
        return
        
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    with mlflow.start_run(run_name="transformer_rul"):
        mlflow.log_param("seq_length", seq_length)
        
        model = TransformerRULModel(n_features=len(features), device=device)
        model.fit(X_train, y_train, epochs=20)
        
        # Evaluate
        preds = model.predict(X_val)
        y_val_np = y_val.numpy()
        
        from sklearn.metrics import mean_squared_error, mean_absolute_error
        import numpy as np
        
        rmse = np.sqrt(mean_squared_error(y_val_np, preds))
        mae = mean_absolute_error(y_val_np, preds)
        
        d = preds - y_val_np
        s_score = np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1))
        
        metrics = {"rmse": rmse, "mae": mae, "s_score": s_score}
        logger.info(f"Transformer Validation Metrics: {metrics}")
        mlflow.log_metrics(metrics)
        
        # Log model (need to wrap for MLflow, or log state dict)
        mlflow.pytorch.log_model(model.model, "model")
        register_model(mlflow.active_run().info.run_id, "factorypulse_rul_transformer")


def main(data_dir: str):
    data_path = Path(data_dir)
    train_file = data_path / "cmapss_featured_train.parquet"
    val_file = data_path / "cmapss_featured_val.parquet"
    
    if not train_file.exists() or not val_file.exists():
        logger.error(f"Data files not found in {data_dir}")
        return
        
    train_df = pd.read_parquet(train_file)
    val_df = pd.read_parquet(val_file)
    
    # Fill any remaining NaNs
    train_df = train_df.fillna(0)
    val_df = val_df.fillna(0)
    
    # Ensure RUL column exists
    if "rul" not in train_df.columns:
        logger.error("Target column 'rul' not found in dataset")
        return
        
    # Setup MLflow
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("factorypulse_rul")
    
    # Train models
    train_xgboost(train_df, val_df)
    train_transformer(train_df, val_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", help="Directory containing featured parquet files")
    args = parser.parse_args()
    main(args.data_dir)
