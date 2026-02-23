#!/usr/bin/env python3

import logging
import time
from typing import Optional

from database import Database
from image import fetch, process
from mqtt_client import create_mqtt_client, send_message
from settings import AppSettings
from signal_handler import setup_signal_handlers
from snow_depth import measure_snow_depth

CONFIG_FILE_NAME = "config.yaml"


def handle_image_brightness(uri: str, logger: logging.Logger) -> float:
    image_bytes = fetch(uri)
    if image_bytes is None:
        logger.warning(f"Failed to fetch image from {uri} for brightness calculation.")
        return 0.0

    value = process(image_bytes)
    logger.debug(f"Got brightness value {value} from {uri}")
    return value


def handle_snow_depth_measurement(
    settings: AppSettings, logger: logging.Logger
) -> Optional[float]:
    if not settings.snow_depth_sensor.enabled:
        return None

    if not settings.snow_depth_sensor.image_uri:
        logger.error("Snow depth sensor enabled but no image_uri configured.")
        return None

    if (
        not settings.snow_depth_sensor.stick_total_cm
        or not settings.snow_depth_sensor.pixels_per_cm
    ):
        logger.error(
            "Snow depth sensor enabled but calibration data (stick_total_cm, pixels_per_cm) missing."
        )
        return None

    logger.info(f"Measuring snow depth from {settings.snow_depth_sensor.image_uri}")
    image_bytes = fetch(settings.snow_depth_sensor.image_uri)
    if image_bytes is None:
        logger.warning(
            f"Failed to fetch image from {settings.snow_depth_sensor.image_uri} for snow depth measurement."
        )
        return None

    # Prepare ROI tuple if configured
    roi = None
    if (
        settings.snow_depth_sensor.roi_x is not None
        and settings.snow_depth_sensor.roi_y is not None
        and settings.snow_depth_sensor.roi_w is not None
        and settings.snow_depth_sensor.roi_h is not None
    ):
        roi = (
            settings.snow_depth_sensor.roi_x,
            settings.snow_depth_sensor.roi_y,
            settings.snow_depth_sensor.roi_w,
            settings.snow_depth_sensor.roi_h,
        )

    snow_depth_cm = measure_snow_depth(
        image_bytes=image_bytes,
        stick_colors=settings.snow_depth_sensor.stick_colors,
        stick_total_cm=settings.snow_depth_sensor.stick_total_cm,
        pixels_per_cm=settings.snow_depth_sensor.pixels_per_cm,
        roi=roi,
        roi_rotation=settings.snow_depth_sensor.roi_rotation,
    )
    return snow_depth_cm


def run_service() -> None:
    # Load configuration
    settings = AppSettings.load(CONFIG_FILE_NAME)

    # Configure logging
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Initialize database
    db = Database()

    # Initialize MQTT client
    client = create_mqtt_client()
    client.connect(settings.mqtt.host, settings.mqtt.port, 60)
    client.loop_start()

    setup_signal_handlers(client)

    logger.info("Service is running...")
    try:
        while True:
            # --- Brightness Sensors ---
            sensors = settings.get_sensors()
            for sensor in sensors:
                logger.info(f"Processing sensor: {sensor.name}")
                total_value = 0.0
                valid_sources = 0

                for image_uri in sensor.sources:
                    val = handle_image_brightness(image_uri, logger)
                    total_value += val
                    valid_sources += 1

                if valid_sources > 0:
                    avg = round(total_value / valid_sources, 2)
                else:
                    avg = 0.0

                logger.debug(f"Sensor {sensor.name} average: {avg}")

                # Database operations
                db.insert_history(sensor.name, avg)

                # Current value
                send_message(client, sensor.topic, avg, logger)

                # Delayed value
                if sensor.delayed_topic and sensor.delay_seconds:
                    delayed_value = db.get_delayed_value(
                        sensor.name, sensor.delay_seconds
                    )
                    if delayed_value is not None:
                        send_message(
                            client,
                            sensor.delayed_topic,
                            round(delayed_value, 2),
                            logger,
                        )

            # --- Snow Depth Measurement ---
            snow_depth = handle_snow_depth_measurement(settings, logger)
            if snow_depth is not None:
                # If legacy topic exists, use it as prefix, otherwise use a default
                base_topic = settings.mqtt.topic or "cameralight"
                snow_depth_topic = f"{base_topic}_snow_depth"
                send_message(client, snow_depth_topic, snow_depth, logger)

            time.sleep(settings.interval)

    except KeyboardInterrupt:
        logger.warning("Service interrupted by KeyboardInterrupt")
    finally:
        client.loop_stop()
        client.disconnect()
        db.close()


if __name__ == "__main__":
    run_service()
