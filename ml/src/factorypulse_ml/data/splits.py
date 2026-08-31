import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def split_data(interim_dir: str, processed_dir: str, train_ratio: float = 0.7, val_ratio: float = 0.15):
    """
    Performs leakage-safe, unit-wise train/val/test splits.
    Ensures that a single machine_id's data entirely falls into one of the splits.
    """
    Path(processed_dir).mkdir(parents=True, exist_ok=True)
    
    interim_path = Path(interim_dir)
    parquet_files = list(interim_path.glob("*.parquet"))
    
    if not parquet_files:
        logger.warning(f"No parquet files found in {interim_dir}")
        return
        
    for p in parquet_files:
        df = pd.read_parquet(p)
        machines = df['machine_id'].unique()
        
        # Shuffle machines
        np.random.seed(42)
        np.random.shuffle(machines)
        
        n = len(machines)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        
        train_machines = machines[:train_end]
        val_machines = machines[train_end:val_end]
        test_machines = machines[val_end:]
        
        # If there's only 1 machine (e.g. dummy data), put it in train
        if n == 1:
            train_machines = machines
            val_machines = []
            test_machines = []
            
        train_df = df[df['machine_id'].isin(train_machines)]
        val_df = df[df['machine_id'].isin(val_machines)]
        test_df = df[df['machine_id'].isin(test_machines)]
        
        dataset_name = p.stem.replace("_canonical", "")
        
        # Always write all three split files — DVC requires declared outputs to exist
        train_df.to_parquet(Path(processed_dir) / f"{dataset_name}_train.parquet", index=False)
        val_df.to_parquet(Path(processed_dir) / f"{dataset_name}_val.parquet", index=False)
        test_df.to_parquet(Path(processed_dir) / f"{dataset_name}_test.parquet", index=False)
            
        logger.info(f"Split {dataset_name}: Train={len(train_machines)}, Val={len(val_machines)}, Test={len(test_machines)} machines.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python splits.py <interim_dir> <processed_dir>")
        sys.exit(1)
    split_data(sys.argv[1], sys.argv[2])
