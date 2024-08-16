import signal
import sys

def setup_signal_handlers(client):
    def signal_handler(sig, frame):
        print("Signal received, shutting down...")
        client.disconnect()
        client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

