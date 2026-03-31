# workers/tilt_controller.py
import socket
import threading
import time
from datetime import datetime
from typing import Callable

from core.pelco_utils import build_tilt_abs

POSITION_TIMEOUT = 5.0
POLL_INTERVAL = 0.1


class TiltController:
    def __init__(self, host: str, port: int, address: int,
                 stop_flag: threading.Event,
                 event_cb: Callable[[str, str, datetime], None]):
        self._host = host
        self._port = port
        self._address = address
        self._stop_flag = stop_flag
        self._event_cb = event_cb
        self._sock: socket.socket | None = None

    def connect(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((self._host, self._port))
            s.settimeout(None)
            self._sock = s
            self._event_cb(
                "TCP Connected",
                f"host={self._host} port={self._port}",
                datetime.now(),
            )
            return True
        except Exception as e:
            self._event_cb("TCP Failed", str(e), datetime.now())
            return False

    def do_tilt_move(self, target: float, stop_flag: threading.Event) -> bool:
        _, abs_pkt = build_tilt_abs(self._address, target)
        try:
            self._sock.sendall(abs_pkt)
        except Exception:
            return False
        deadline = time.monotonic() + POSITION_TIMEOUT
        while time.monotonic() < deadline:
            if stop_flag.is_set():
                return False
            time.sleep(POLL_INTERVAL)
        return True

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
