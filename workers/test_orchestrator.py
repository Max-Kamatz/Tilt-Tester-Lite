# workers/test_orchestrator.py
import time
import threading
from datetime import datetime
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from workers.tilt_controller import TiltController

DWELL_SECONDS = 0.5
TILT_NEGATIVE = -90.0
TILT_POSITIVE = 90.0


class TestOrchestrator(QThread):
    test_event = pyqtSignal(str, str, object)   # source, event_type, timestamp
    cycle_updated = pyqtSignal(int, int)         # current_cycle, total_cycles
    test_finished = pyqtSignal(str)              # reason

    def __init__(self, host: str, pelco_port: int, address: int,
                 total_cycles: int, stop_flag: threading.Event,
                 parent=None):
        super().__init__(parent)
        self._host = host
        self._pelco_port = pelco_port
        self._address = address
        self._total_cycles = total_cycles
        self._stop_flag = stop_flag

    def _make_tilt_controller(self) -> TiltController:
        return TiltController(
            self._host, self._pelco_port, self._address,
            self._stop_flag, self._emit_tcp_event,
        )

    def _emit_tcp_event(self, event_type: str, detail: str,
                        ts: datetime) -> None:
        self.test_event.emit("PTZ", event_type, ts)

    def _emit(self, source: str, event_type: str, detail: str = "") -> None:
        self.test_event.emit(source, event_type, datetime.now())

    def run(self) -> None:
        tc = self._make_tilt_controller()
        if not tc.connect():
            return

        self._emit("PTZ", "Test Start")
        cycle = 0

        while cycle < self._total_cycles and not self._stop_flag.is_set():
            for target in (TILT_NEGATIVE, TILT_POSITIVE):
                if self._stop_flag.is_set():
                    break
                reached = tc.do_tilt_move(target, self._stop_flag)
                if not reached:
                    self._emit("PTZ", "Position Failure",
                               f"target={target}")
                else:
                    self._emit("PTZ", "Position Reached",
                               f"tilt={target}")
                if not self._stop_flag.is_set():
                    time.sleep(DWELL_SECONDS)

            if not self._stop_flag.is_set():
                cycle += 1
                self._emit("PTZ", "Cycle Complete", f"cycle={cycle}")
                self.cycle_updated.emit(cycle, self._total_cycles)

        if self._stop_flag.is_set():
            reason = "User stopped" if not (cycle >= self._total_cycles) \
                else "Cycle count reached"
        else:
            reason = "Cycle count reached"

        self._emit("PTZ", "Test Stop", reason)
        tc.close()
        self.test_finished.emit(reason)
