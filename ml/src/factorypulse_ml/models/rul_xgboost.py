"""XGBoost model for Remaining Useful Life (RUL) prediction."""
import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error

logger = logging.getLogger(__name__)


class RULXGBoost:
    """XGBoost Regressor for RUL prediction using tabular features."""

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {
            "objective": "reg:squarederror",
            "max_depth": 5,
            "learning_rate": 0.05,
            "n_estimators": 100,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        self.model = xgb.XGBRegressor(**self.params)
        self.feature_names = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RULXGBoost":
        """Train the model."""
        self.feature_names = list(X.columns)
        logger.info("Training XGBoost RUL model with %d features and %d samples", len(self.feature_names), len(X))
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict RUL."""
        if self.feature_names is not None:
            # Ensure columns match training
            X = X[self.feature_names]
        
        preds = self.model.predict(X)
        # RUL cannot be negative
        return np.maximum(preds, 0)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate the model and return metrics."""
        preds = self.predict(X)
        rmse = np.sqrt(mean_squared_error(y, preds))
        mae = mean_absolute_error(y, preds)
        
        # Asymmetric scoring function (S-score) often used for C-MAPSS
        # Penalizes late predictions (overestimating RUL) more than early predictions
        d = preds - y
        s_score = np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1))
        
        return {
            "rmse": float(rmse),
            "mae": float(mae),
            "s_score": float(s_score)
        }

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance scores."""
        if self.model is None or self.feature_names is None:
            return pd.DataFrame()
            
        importance = self.model.feature_importances_
        df = pd.DataFrame({
            "feature": self.feature_names,
            "importance": importance
        }).sort_values("importance", ascending=False)
        return df
