#!/usr/bin/env python3

from mqtt_client import create_mqtt_client, send_message
from signal_handler import setup_signal_handlers
from config import load_config
import time
from image import fetch, process
import logging
import sqlite3

CONFIG_FILE_NAME = "config.yaml"

config = load_config(CONFIG_FILE_NAME)
log_level = config.get('log_level', 'WARNING').upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS history (ts INTEGER, value REAL)''')

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
            avg = round(result/len(config['images']), 2)
            logger.debug(f"Avg {avg}")
            current_timestamp = int(time.time())
            cursor.execute("INSERT INTO history (ts, value) VALUES (?, ?)", (current_timestamp, avg))
            conn.commit()
            delayed_ts = int(time.time()) - (23 * 60 * 60)
            cursor.execute("SELECT value FROM history WHERE ts < ? ORDER BY ts ASC LIMIT 1", (delayed_ts,))
            row = cursor.fetchone()
            if row:
                send_message(client, config['mqtt']['topic'] + "_delayed", round(row[0], 2))
            send_message(client, config['mqtt']['topic'], avg)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.warning("Service interrupted by KeyboardInterrupt")
    finally:
        client.loop_stop()
        client.disconnect()
        conn.close()


if __name__ == "__main__":
    run_service()

