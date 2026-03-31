# workers/tilt_controller.py
import socket
import threading
import time
from datetime import datetime
from typing import Callable

from core.pelco_utils import build_tilt_abs, build_query_tilt, decode_tilt_response

POSITION_TIMEOUT = 5.0
POLL_INTERVAL = 0.1
TOLERANCE_DEG = 1.0
RECV_BUF = 256


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
        self._latest_tilt: float | None = None
        self._tilt_lock = threading.Lock()
        self._recv_thread: threading.Thread | None = None

    def connect(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((self._host, self._port))
            self._sock = s
            self._start_recv_thread()
            self._event_cb(
                "TCP Connected",
                f"host={self._host} port={self._port}",
                datetime.now(),
            )
            return True
        except Exception as e:
            self._event_cb("TCP Failed", str(e), datetime.now())
            return False

    def _start_recv_thread(self) -> None:
        self._recv_thread = threading.Thread(
            target=self._recv_loop, daemon=True
        )
        self._recv_thread.start()

    def _recv_loop(self) -> None:
        while not self._stop_flag.is_set():
            try:
                data = self._sock.recv(RECV_BUF)
                if not data:
                    break
                tilt = decode_tilt_response(data)
                if tilt is not None:
                    with self._tilt_lock:
                        self._latest_tilt = tilt
            except Exception:
                break

    def do_tilt_move(self, target: float, stop_flag: threading.Event) -> bool:
        prime, abs_pkt = build_tilt_abs(self._address, target)
        self._sock.sendall(prime)
        self._sock.sendall(abs_pkt)
        deadline = time.monotonic() + POSITION_TIMEOUT
        while time.monotonic() < deadline:
            if stop_flag.is_set():
                return False
            query = build_query_tilt(self._address)
            try:
                self._sock.sendall(query)
            except Exception:
                return False
            time.sleep(POLL_INTERVAL)
            with self._tilt_lock:
                current = self._latest_tilt
            if current is not None and abs(current - target) <= TOLERANCE_DEG:
                return True
        return False

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
