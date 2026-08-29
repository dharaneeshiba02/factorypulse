import json
import logging
import httpx
import paho.mqtt.client as mqtt
from typing import List, Dict

logger = logging.getLogger(__name__)

class Transport:
    def publish(self, payload: List[Dict]):
        raise NotImplementedError

class MQTTTransport(Transport):
    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        
    def publish(self, payload: List[Dict]):
        # The schema expects a batch: {"readings": [...]}
        msg = json.dumps({"readings": payload})
        self.client.publish(self.topic, msg)
        logger.debug(f"Published {len(payload)} readings to MQTT topic {self.topic}")

class HTTPTransport(Transport):
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.client = httpx.Client()
        
    def publish(self, payload: List[Dict]):
        msg = {"readings": payload}
        try:
            resp = self.client.post(self.target_url, json=msg)
            resp.raise_for_status()
            logger.debug(f"Published {len(payload)} readings to HTTP {self.target_url}")
        except Exception as e:
            logger.error(f"HTTP publish failed: {e}")

def get_transport(config) -> Transport:
    if config.transport_type.lower() == "mqtt":
        return MQTTTransport(config.mqtt_broker, config.mqtt_port, config.mqtt_topic)
    elif config.transport_type.lower() == "http":
        return HTTPTransport(config.http_target_url)
    else:
        raise ValueError(f"Unknown transport type: {config.transport_type}")
