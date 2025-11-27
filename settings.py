import os
from typing import List

import yaml
from pydantic import BaseModel


class MqttConfig(BaseModel):
    host: str
    port: int
    topic: str


class AppSettings(BaseModel):
    log_level: str = "WARNING"
    interval: int = 60
    images: List[str]
    mqtt: MqttConfig

    @classmethod
    def load(cls, filename: str = "config.yaml") -> "AppSettings":
        with open(filename, "r") as f:
            config_data = yaml.safe_load(f)

        # Override with environment variables (Legacy support)
        if "mqtt" in config_data:
            config_data["mqtt"]["host"] = os.getenv(
                "MQTT_HOST", config_data["mqtt"].get("host")
            )
            config_data["mqtt"]["port"] = os.getenv(
                "MQTT_PORT", config_data["mqtt"].get("port")
            )

        config_data["interval"] = os.getenv("INTERVAL", config_data.get("interval"))

        return cls(**config_data)
