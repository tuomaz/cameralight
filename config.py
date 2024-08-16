import yaml
import os

def load_config(filename):
    with open(filename, 'r') as f:
        config = yaml.safe_load(f)


    config['mqtt']['host'] = os.getenv('MQTT_HOST', config['mqtt']['host'])
    config['mqtt']['port'] = os.getenv('MQTT_PORT', config['mqtt']['port'])
    config['interval'] = os.getenv('INTERVAL', config['interval'])

    return config
