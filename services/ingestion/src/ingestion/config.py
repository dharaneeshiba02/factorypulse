"""Typed settings for ingestion, persistence, and online feature generation."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", extra="ignore")

    database_url: str = "postgresql://factorypulse:change-me-local-only@localhost:5432/factorypulse"
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "factorypulse/telemetry"
    redis_url: str = "redis://localhost:6379/0"
    batch_size: int = 500
    flush_interval_seconds: float = 1.0
    max_sensor_value: float = 1e6
    min_quality: int = 0
    feature_history_size: int = 50
    feature_cache_ttl_seconds: int = 3600
    api_host: str = "0.0.0.0"
    api_port: int = 8000


config = IngestionConfig()
