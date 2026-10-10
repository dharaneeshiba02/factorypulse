"""Generate HTML/JSON evaluation reports."""
import json
import logging
from pathlib import Path
from typing import Dict, Any

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

def generate_report(metrics: Dict[str, Any], output_dir: str, name: str = "report"):
    """Generate a JSON metrics report."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    report_file = out_path / f"{name}.json"
    with open(report_file, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Saved report to {report_file}")
    
def plot_predictions(y_true, y_pred, output_dir: str, name: str = "predictions"):
    """Generate a scatter plot of true vs predicted values."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    plt.figure(figsize=(10, 6))
    plt.scatter(y_true, y_pred, alpha=0.5)
    plt.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--')
    plt.xlabel('True Values')
    plt.ylabel('Predictions')
    plt.title('True vs Predicted')
    
    plot_file = out_path / f"{name}.png"
    plt.savefig(plot_file)
    plt.close()
    logger.info(f"Saved plot to {plot_file}")
