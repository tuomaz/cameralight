import signal
import sys
from typing import Any


def setup_signal_handlers(client: Any) -> None:
    def signal_handler(sig: int, frame: Any) -> None:
        print("Signal received, shutting down...")
        client.disconnect()
        client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
