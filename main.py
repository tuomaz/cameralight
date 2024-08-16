#!/usr/bin/env python3

from mqtt_client import create_mqtt_client
from signal_handler import setup_signal_handlers
import time

def run_service():
    client = create_mqtt_client()
    client.connect("mqtt.eclipse.org", 1883, 60)
    client.loop_start()

    setup_signal_handlers(client)

    print("Service is running...")
    try:
        while True:
            client.publish("test/topic", "Hello MQTT!")
            time.sleep(10)
    except KeyboardInterrupt:
        print("Service interrupted by KeyboardInterrupt")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_service()

