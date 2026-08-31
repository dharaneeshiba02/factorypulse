"""MQTT consumer — subscribes to the telemetry topic and feeds the batch writer."""
import json
import logging
import threading
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt
from ingestion.config import config
from ingestion.schemas import TelemetryReading
from ingestion.validators import validate_batch

if TYPE_CHECKING:
    from ingestion.writer import BatchWriter

logger = logging.getLogger(__name__)


class MQTTConsumer:
    """Subscribes to an MQTT topic and validates + enqueues readings."""

    def __init__(self, writer: "BatchWriter", loop):
        self.writer = writer
        self.loop = loop  # asyncio event loop for scheduling coroutines
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self):
        """Connect and start the network loop in a background thread."""
        try:
            self.client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)
            self.client.loop_start()
            logger.info(
                "MQTT consumer connected to %s:%d", config.mqtt_broker, config.mqtt_port
            )
        except Exception:
            logger.exception("Failed to connect to MQTT broker")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    # ---- callbacks ----

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(config.mqtt_topic)
            logger.info("Subscribed to %s", config.mqtt_topic)
        else:
            logger.error("MQTT connect failed with code %d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            raw_readings = payload.get("readings", [])
            readings = [TelemetryReading(**r) for r in raw_readings]
            valid, errors = validate_batch(readings)

            if valid:
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    self.writer.enqueue(valid), self.loop
                )

            if errors:
                logger.warning("Rejected %d readings: %s", len(errors), errors[:3])

        except Exception:
            logger.exception("Error processing MQTT message")
