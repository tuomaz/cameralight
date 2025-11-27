import os
import yaml
from typing import List, Optional
from pydantic import BaseModel


class MqttConfig(BaseModel):
    host: str
    port: int
    topic: str


class SnowDepthSensorConfig(BaseModel):
    enabled: bool = False
    image_uri: Optional[str] = None
    stick_colors: List[str] = []
    stick_total_cm: float = 0.0 # Total physical length of the stick
    pixels_per_cm: float = 0.0 # Calibration factor


class AppSettings(BaseModel):
    log_level: str = "WARNING"
    interval: int = 60
    images: List[str]
    mqtt: MqttConfig
    snow_depth_sensor: SnowDepthSensorConfig = SnowDepthSensorConfig()

    @classmethod
    def load(cls, filename: str = "config.yaml") -> "AppSettings":
        with open(filename, "r") as f:
            config_data = yaml.safe_load(f)

        if "mqtt" in config_data:
            config_data["mqtt"]["host"] = os.getenv(
                "MQTT_HOST", config_data["mqtt"].get("host")
            )
            config_data["mqtt"]["port"] = os.getenv(
                "MQTT_PORT", config_data["mqtt"].get("port")
            )
        
        config_data["interval"] = os.getenv("INTERVAL", config_data.get("interval"))

        return cls(**config_data)