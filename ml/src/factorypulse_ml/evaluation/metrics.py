"""Evaluation metrics for predictive maintenance models."""
import numpy as np

def score_rul(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate the asymmetric scoring function used in PHM08 Challenge.
    Penalizes late predictions (RUL > true RUL, potentially leading to failure)
    more heavily than early predictions.
    """
    d = y_pred - y_true
    score = np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1))
    return float(score)

def calculate_metrics(y_true, y_pred):
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "score": score_rul(y_true, y_pred)
    }
