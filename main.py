#!/usr/bin/env python3

import logging
import time

from database import Database
from image import fetch, process
from mqtt_client import create_mqtt_client, send_message
from settings import AppSettings
from signal_handler import setup_signal_handlers

CONFIG_FILE_NAME = "config.yaml"


def handle(uri: str, logger: logging.Logger) -> float:
    image_bytes = fetch(uri)
    if image_bytes is None:
        logger.warning(f"Failed to fetch image from {uri}")
        return 0.0

    value = process(image_bytes)
    logger.debug(f"Got value {value} from {uri}")
    return value


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

    interval = settings.interval * 60

    logger.info("Service is running...")
    try:
        while True:
            sensors = settings.get_sensors()
            for sensor in sensors:
                logger.info(f"Processing sensor: {sensor.name}")
                total_value = 0.0
                valid_sources = 0

                for image_uri in sensor.sources:
                    val = handle(image_uri, logger)
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

            time.sleep(settings.interval)

    except KeyboardInterrupt:
        logger.warning("Service interrupted by KeyboardInterrupt")
    finally:
        client.loop_stop()
        client.disconnect()
        db.close()


if __name__ == "__main__":
    run_service()
