#!/usr/bin/env python3

from mqtt_client import create_mqtt_client, send_message
from signal_handler import setup_signal_handlers
from config import load_config
import time
from image import fetch, process
import logging

CONFIG_FILE_NAME = "config.yaml"

config = load_config(CONFIG_FILE_NAME)
log_level = config.get('log_level', 'WARNING').upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def handle(uri):
    image_bytes = fetch(uri)
    value = process(image_bytes)
    logger.debug(f"Got value is {value} from {uri}")
    return value

def run_service():

    client = create_mqtt_client()
    client.connect(config['mqtt']['host'], config['mqtt']['port'], 60)
    client.loop_start()

    setup_signal_handlers(client)

    interval = 60 * config['interval']

    logger.info("Service is running...")
    try:
        while True:
            result = 0
            for image in config['images']:
                result += handle(image)
            avg = result/len(config['images'])
            logger.debug(f"Avg {avg}")
            send_message(client, config['mqtt']['topic'], avg)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.warning("Service interrupted by KeyboardInterrupt")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_service()

