import pandas as pd
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from simulator.transports import Transport
from simulator.fault_injector import FaultInjector

logger = logging.getLogger(__name__)

class Replayer:
    def __init__(self, data_dir: str, transport: Transport, rate_hz: float, 
                 machine_count: int = -1, injector: FaultInjector = None):
        self.data_dir = Path(data_dir)
        self.transport = transport
        self.rate_hz = rate_hz
        self.machine_count = machine_count
        self.injector = injector
        
    def _load_data(self) -> pd.DataFrame:
        files = list(self.data_dir.glob("*_train.parquet")) + list(self.data_dir.glob("*_val.parquet")) + list(self.data_dir.glob("*_test.parquet"))
        if not files:
            logger.warning(f"No processed data found in {self.data_dir}. Using dummy data stream.")
            return self._generate_dummy_stream()
            
        dfs = []
        for f in files:
            dfs.append(pd.read_parquet(f))
            
        df = pd.concat(dfs, ignore_index=True)
        
        if self.machine_count > 0:
            machines = df['machine_id'].unique()[:self.machine_count]
            df = df[df['machine_id'].isin(machines)]
            
        # Sort chronologically
        df = df.sort_values('time')
        return df

    def _generate_dummy_stream(self) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            'time': [now] * 10,
            'machine_id': ['DUMMY_1'] * 10,
            'sensor': [f'sensor_{i}' for i in range(10)],
            'value': [float(i) for i in range(10)],
            'quality': [100] * 10
        })
        return df
        
    def start(self):
        df = self._load_data()
        
        # We need to simulate the passage of time.
        # Instead of grouping by the original timestamp, we'll just emit batches 
        # at the target Hz. 
        batch_size = 10 # Emit 10 readings per interval
        sleep_interval = 1.0 / self.rate_hz
        
        logger.info(f"Starting replay at {self.rate_hz} Hz...")
        
        readings = df.to_dict(orient='records')
        
        for i in range(0, len(readings), batch_size):
            batch = readings[i:i+batch_size]
            
            # Update timestamps to 'now' so it looks like live data
            now_iso = datetime.now(timezone.utc).isoformat()
            
            payload = []
            for r in batch:
                r['time'] = now_iso # replace original time
                if self.injector:
                    r = self.injector.inject(r)
                payload.append(r)
                
            self.transport.publish(payload)
            time.sleep(sleep_interval)
            
        logger.info("Replay finished.")
