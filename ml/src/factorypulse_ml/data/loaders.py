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
    if not raw_path.exists():
        logger.warning(f"C-MAPSS data not found at {raw_path}. Returning empty DF.")
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
        # Create dummy data for now so the pipeline can proceed without actual data
        logger.info("Creating dummy dataset since real data is missing...")
        dummy = pd.DataFrame({
            'time': [datetime(2025,1,1), datetime(2025,1,2)],
            'machine_id': ['DUMMY_1', 'DUMMY_1'],
            'sensor': ['sensor_1', 'sensor_1'],
            'value': [10.0, 11.5],
            'quality': [100, 100]
        })
        dummy.to_parquet(Path(interim_dir) / "dummy_canonical.parquet", index=False)
        
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python loaders.py <raw_dir> <interim_dir>")
        sys.exit(1)
    run_loaders(sys.argv[1], sys.argv[2])
