"""MQTT transport adapter for the shared telemetry ingestion path."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from ingestion.config import config
from ingestion.schemas import TelemetryReading

if TYPE_CHECKING:
    from ingestion.writer import BatchWriter

logger = logging.getLogger(__name__)


class MQTTConsumer:
    """Subscribe to a telemetry topic and forward parsed batches to the writer."""

    def __init__(self, writer: BatchWriter, loop: asyncio.AbstractEventLoop) -> None:
        self.writer = writer
        self.loop = loop
        self.connected = False
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self) -> None:
        self._worker = self.loop.create_task(self._consume_queue())
        try:
            self.client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)
            self.client.loop_start()
        except Exception:
            self.connected = False
            logger.exception("Could not connect to MQTT broker %s", config.mqtt_broker)

    async def stop(self) -> None:
        self.client.loop_stop()
        await self._queue.join()
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        try:
            self.client.disconnect()
        finally:
            self.connected = False

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        self.connected = rc == 0
        if self.connected:
            client.subscribe(config.mqtt_topic, qos=1)
            logger.info("Subscribed to MQTT topic %s", config.mqtt_topic)
        else:
            logger.error("MQTT connection failed with result code %s", rc)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        self.connected = False
        if rc:
            logger.warning("MQTT disconnected unexpectedly (code %s)", rc)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            raw = message.payload.decode("utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not isinstance(payload.get("readings"), list):
                raise ValueError("message must contain a readings array")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            asyncio.run_coroutine_threadsafe(
                self.writer.record_dead_letter(
                    {"payload": repr(message.payload)}, "mqtt_payload", str(error)
                ),
                self.loop,
            )
            return

        self.loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    async def _consume_queue(self) -> None:
        """Process broker messages in arrival order to preserve stream time."""
        while True:
            payload = await self._queue.get()
            try:
                await self._process_payload(payload)
            except Exception:
                logger.exception("Could not process MQTT telemetry payload")
            finally:
                self._queue.task_done()

    async def _process_payload(self, payload: dict[str, Any]) -> None:
        readings: list[TelemetryReading] = []
        for item in payload["readings"]:
            try:
                readings.append(TelemetryReading.model_validate(item))
            except (ValidationError, TypeError, ValueError) as error:
                await self.writer.record_dead_letter(item, "schema", str(error))
        if readings:
            await self.writer.ingest(readings, raw_payload=payload)
