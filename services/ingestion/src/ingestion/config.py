from pydantic_settings import BaseSettings


class IngestionConfig(BaseSettings):
    """Configuration for the ingestion service."""

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/factorypulse"

    # MQTT
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "factorypulse/telemetry"

    # Redis (for dedup / rate limiting)
    redis_url: str = "redis://localhost:6379/0"

    # Batch writer settings
    batch_size: int = 500
    flush_interval_seconds: float = 1.0

    # Validation
    max_sensor_value: float = 1e6
    min_quality: int = 0

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_prefix = "INGEST_"


config = IngestionConfig()
