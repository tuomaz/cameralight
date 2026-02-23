import os
from typing import List, Optional

import yaml
from pydantic import BaseModel, model_validator


class MqttConfig(BaseModel):
    host: str
    port: int
    topic: Optional[str] = None


class SensorConfig(BaseModel):
    name: str
    sources: List[str]
    topic: str
    delay_seconds: Optional[int] = None
    delayed_topic: Optional[str] = None


class SnowDepthSensorConfig(BaseModel):
    enabled: bool = False
    image_uri: Optional[str] = None
    stick_colors: List[str] = []
    stick_total_cm: float = 0.0  # Total physical length of the stick
    pixels_per_cm: float = 0.0  # Calibration factor
    roi_x: Optional[int] = None
    roi_y: Optional[int] = None
    roi_w: Optional[int] = None
    roi_h: Optional[int] = None
    roi_rotation: float = 0.0  # Degrees to rotate the ROI to make the stick vertical


class AppSettings(BaseModel):
    log_level: str = "WARNING"
    interval: int = 60
    images: Optional[List[str]] = None
    mqtt: MqttConfig
    sensors: Optional[List[SensorConfig]] = None
    snow_depth_sensor: SnowDepthSensorConfig = SnowDepthSensorConfig()

    @model_validator(mode="after")
    def check_at_least_one_sensor_source(self) -> "AppSettings":
        if not self.sensors and not self.images:
            raise ValueError("At least one sensor or images list must be provided")
        if not self.sensors and not self.mqtt.topic:
            raise ValueError("If sensors list is not provided, mqtt.topic must be set")
        return self

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
                "MQTT_PORT", int(config_data["mqtt"].get("port"))
            )

        config_data["interval"] = int(os.getenv("INTERVAL", config_data.get("interval")))

        return cls(**config_data)

    def get_sensors(self) -> List[SensorConfig]:
        """Returns a unified list of sensors, including legacy config converted to a sensor."""
        result = []
        if self.sensors:
            result.extend(self.sensors)

        if self.images and self.mqtt.topic:
            # Add legacy config as a 'default' sensor
            result.append(
                SensorConfig(
                    name="default",
                    sources=self.images,
                    topic=self.mqtt.topic,
                    delay_seconds=81000,  # 22.5 hours legacy default
                    delayed_topic=f"{self.mqtt.topic}_delayed",
                )
            )
        return result
