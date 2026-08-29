from pydantic_settings import BaseSettings

class SimulatorConfig(BaseSettings):
    # Replay configuration
    data_dir: str = "data/processed"
    replay_rate_hz: float = 10.0
    machine_count: int = -1 # -1 means all available in the dataset
    
    # Transport configuration
    transport_type: str = "mqtt" # mqtt or http
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "factorypulse/telemetry"
    
    http_target_url: str = "http://localhost:8000/api/v1/telemetry"
    
    # Fault injection
    inject_faults: bool = False
    fault_probability: float = 0.05
    
    class Config:
        env_prefix = "SIM_"
        
config = SimulatorConfig()
