"""LightGBM model for failure-mode classification."""
import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)


class FailureClassifierLGBM:
    """LightGBM Classifier for failure mode prediction."""

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {
            "objective": "multiclass",
            "num_class": 4, # Normal + 3 failure modes
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": -1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_estimators": 100,
            "verbose": -1
        }
        self.model = lgb.LGBMClassifier(**self.params)
        self.feature_names = None
        self.classes = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FailureClassifierLGBM":
        """Train the model."""
        self.feature_names = list(X.columns)
        self.classes = np.unique(y)
        
        # Ensure num_class is set correctly
        if len(self.classes) > 2:
            self.model.set_params(num_class=len(self.classes), objective="multiclass")
        else:
            self.model.set_params(objective="binary")
            
        logger.info("Training LightGBM failure classifier with %d features and %d samples", len(self.feature_names), len(X))
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict failure mode class."""
        if self.feature_names is not None:
            X = X[self.feature_names]
        return self.model.predict(X)
        
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities."""
        if self.feature_names is not None:
            X = X[self.feature_names]
        return self.model.predict_proba(X)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate the model and return metrics."""
        preds = self.predict(X)
        
        # Determine average parameter based on number of classes
        avg_type = "weighted" if len(self.classes) > 2 else "binary"
        
        acc = accuracy_score(y, preds)
        prec = precision_score(y, preds, average=avg_type, zero_division=0)
        rec = recall_score(y, preds, average=avg_type, zero_division=0)
        f1 = f1_score(y, preds, average=avg_type, zero_division=0)
        
        return {
            "accuracy": float(acc),
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1)
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
