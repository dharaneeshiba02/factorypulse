import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

from factorypulse_ml.data.canonical import validate_dataframe

logger = logging.getLogger(__name__)

def load_cmapss(raw_dir: str) -> pd.DataFrame:
    """
    Loads C-MAPSS FD001 dataset and transforms to canonical format.
    Assumes `train_FD001.txt` is in raw_dir.
    """
    raw_path = Path(raw_dir) / "train_FD001.txt"
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        logger.warning(f"C-MAPSS data missing or empty at {raw_path}. Returning empty DF.")
        return pd.DataFrame(columns=['time', 'machine_id', 'sensor', 'value', 'quality'])
        
    # Standard column names for C-MAPSS
    cols = ['unit', 'cycle', 'op_setting_1', 'op_setting_2', 'op_setting_3'] + \
           [f'sensor_{i}' for i in range(1, 22)]
           
    df = pd.read_csv(raw_path, sep=r'\s+', header=None, names=cols)
    
    # Map to canonical schema
    # Assume 1 cycle = 1 hour for timestamps, starting at some baseline date
    baseline_time = datetime(2025, 1, 1)
    df['time'] = df['cycle'].apply(lambda c: baseline_time + timedelta(hours=c))
    
    # Melt the sensor columns to long format
    id_vars = ['time', 'unit']
    value_vars = [f'sensor_{i}' for i in range(1, 22)]
    melted = df.melt(id_vars=id_vars, value_vars=value_vars, var_name='sensor', value_name='value')
    
    melted['machine_id'] = melted['unit'].apply(lambda u: f"CMAPSS_UNIT_{u}")
    melted['quality'] = 100
    
    return validate_dataframe(melted[['time', 'machine_id', 'sensor', 'value', 'quality']])

def run_loaders(raw_dir: str, interim_dir: str):
    """Entrypoint to run all loaders and save to interim parquet."""
    Path(interim_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info("Loading C-MAPSS...")
    df_cmapss = load_cmapss(raw_dir)
    
    if not df_cmapss.empty:
        out_path = Path(interim_dir) / "cmapss_canonical.parquet"
        df_cmapss.to_parquet(out_path, index=False)
        logger.info(f"Saved C-MAPSS canonical data to {out_path}")
    else:
        # Create dummy data with enough machines for a 3-way split
        logger.info("Creating dummy dataset since real data is missing...")
        rows = []
        for i in range(1, 5):  # 4 machines → train gets 2, val gets 1, test gets 1
            for j in range(3):  # 3 readings per machine
                rows.append({
                    'time': datetime(2025, 1, 1) + timedelta(hours=j),
                    'machine_id': f'DUMMY_{i}',
                    'sensor': 'sensor_1',
                    'value': 10.0 + i + j * 0.5,
                    'quality': 100,
                })
        dummy = pd.DataFrame(rows)
        out_path = Path(interim_dir) / "cmapss_canonical.parquet"
        dummy.to_parquet(out_path, index=False)
        logger.info(f"Saved dummy canonical data to {out_path}")
        
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python loaders.py <raw_dir> <interim_dir>")
        sys.exit(1)
    run_loaders(sys.argv[1], sys.argv[2])
