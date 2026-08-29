import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid

class TelemetryReading(BaseModel):
    """Canonical schema for a single telemetry reading from a sensor."""
    model_config = ConfigDict(populate_by_name=True)

    time: datetime
    machine_id: str
    sensor: str
    value: float
    quality: int = Field(default=100, ge=0, le=100)

class TelemetryBatch(BaseModel):
    """A batch of canonical telemetry readings."""
    readings: List[TelemetryReading]

def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validates a pandas DataFrame against the canonical schema.
    Required columns: ['time', 'machine_id', 'sensor', 'value', 'quality']
    """
    required_cols = ['time', 'machine_id', 'sensor', 'value', 'quality']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in dataframe: {missing}")
        
    df = df[required_cols].copy()
    df['time'] = pd.to_datetime(df['time'])
    df['machine_id'] = df['machine_id'].astype(str)
    df['sensor'] = df['sensor'].astype(str)
    df['value'] = df['value'].astype(float)
    df['quality'] = df['quality'].astype(int)
    
    return df
