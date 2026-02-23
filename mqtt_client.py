from logging import Logger
from typing import Any

import paho.mqtt.client as mqtt


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
    print(f"Connected with result code {rc}")
    client.subscribe("test/topic")


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    print(f"Message received on {msg.topic}: {msg.payload.decode()}")


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    return client


def send_message(client: mqtt.Client, topic: str, value: float, logger: Logger) -> None:
    logger.info(f"Sending MQTT message: topic={topic}, value={value}")
    client.publish(topic, value)
