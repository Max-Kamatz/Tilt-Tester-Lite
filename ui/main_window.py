# ui/main_window.py
import threading
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSpinBox, QSplitter,
    QVBoxLayout, QWidget, QLineEdit, QFileDialog,
)

from logger.test_logger import TestLogger
from ui.device_tile import DeviceTile
from ui.event_log import EventLog
from workers.ping_monitor import PingMonitor, DEVICES, probe_active_devices
from workers.test_orchestrator import TestOrchestrator

_STYLE = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }
QLineEdit, QSpinBox { background: #161b22; color: #c9d1d9; border: 1px solid #30363d; }
QPushButton { background: #3277ff; color: #fff; border: none; padding: 4px 10px; border-radius: 3px; }
QPushButton:disabled { background: #1c2333; color: #555; }
"""


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tilt Tester Lite")
        self.setStyleSheet(_STYLE)
        self._logger = TestLogger()
        self._stop_flag = threading.Event()
        self._ping_monitor: PingMonitor | None = None
        self._orchestrator: TestOrchestrator | None = None
        self._ever_connectivity_loss: set[str] = set()
        self._active_devices: list[str] = list(DEVICES)
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_body(), stretch=1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self._ip_field = QLineEdit("192.168.1.100")
        self._ip_field.setPlaceholderText("IP Address")
        self._ssh_port = QSpinBox(); self._ssh_port.setRange(1, 65535)
        self._ssh_port.setValue(22); self._ssh_port.setPrefix("SSH:")
        self._ssh_user = QLineEdit("silentsentinel"); self._ssh_user.setPlaceholderText("SSH User")
        self._ssh_pass = QLineEdit("Sentinel123"); self._ssh_pass.setPlaceholderText("SSH Pass")
        self._ssh_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._pelco_port = QSpinBox(); self._pelco_port.setRange(1, 65535)
        self._pelco_port.setValue(34010); self._pelco_port.setPrefix("Pelco:")
        self._pelco_addr = QSpinBox(); self._pelco_addr.setRange(1, 255)
        self._pelco_addr.setValue(1); self._pelco_addr.setPrefix("Addr:")
        self._cycles_spin = QSpinBox(); self._cycles_spin.setRange(1, 99999)
        self._cycles_spin.setValue(100); self._cycles_spin.setPrefix("Cycles:")

        self._btn_start = QPushButton("Start")
        self._btn_stop = QPushButton("Stop"); self._btn_stop.setEnabled(False)
        self._btn_export = QPushButton("Export"); self._btn_export.setEnabled(False)
        self._status_label = QLabel("Idle")

        for w in (self._ip_field, self._ssh_port, self._ssh_user,
                  self._ssh_pass, self._pelco_port, self._pelco_addr,
                  self._cycles_spin, self._btn_start, self._btn_stop,
                  self._btn_export, self._status_label):
            layout.addWidget(w)
        layout.addStretch()

        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_export.clicked.connect(self._on_export)
        return bar

    def _build_body(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._tiles: dict[str, DeviceTile] = {}
        for ip in DEVICES:
            tile = DeviceTile(ip)
            self._tiles[ip] = tile
            left_layout.addWidget(tile)
        left_layout.addStretch()
        self._event_log = EventLog()
        splitter.addWidget(left)
        splitter.addWidget(self._event_log)
        splitter.setStretchFactor(1, 3)
        return splitter

    # ── Button Handlers ───────────────────────────────────────────────

    def _on_start(self) -> None:
        self._stop_flag.clear()
        self._ever_connectivity_loss.clear()
        for tile in self._tiles.values():
            tile.reset()
        self._event_log.clear()

        self._status_label.setText("Probing devices...")
        QApplication.processEvents()
        self._active_devices = probe_active_devices(
            self._ip_field.text(), self._ssh_port.value(),
            self._ssh_user.text(), self._ssh_pass.text(),
        )
        for ip, tile in self._tiles.items():
            if ip not in self._active_devices:
                tile.set_status("Not Present")

        self._logger.start()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._status_label.setText(f"Running — Cycle 0 / {self._cycles_spin.value()}")
        self._start_ping_monitor()
        self._start_orchestrator()

    def _on_stop(self) -> None:
        self._stop_flag.set()
        self._status_label.setText("Stopped")
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(True)

    def _on_export(self) -> None:
        from datetime import datetime as dt
        default = dt.now().strftime("TiltTesterLite_%Y%m%d_%H%M%S")
        path, filt = QFileDialog.getSaveFileName(
            self, "Export", default, "CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path:
            return
        if "xlsx" in filt:
            self._logger.export_excel(path)
        else:
            self._logger.export_csv(path)

    # ── Worker Setup ─────────────────────────────────────────────────

    def _start_ping_monitor(self) -> None:
        self._ping_monitor = PingMonitor(
            self._ip_field.text(), self._ssh_port.value(),
            self._ssh_user.text(), self._ssh_pass.text(),
            self._stop_flag, self._active_devices,
        )
        self._ping_monitor.ping_loss_event.connect(self._on_ping_loss_event)
        self._ping_monitor.connection_event.connect(self._on_connection_event)
        self._ping_monitor.start()

    def _start_orchestrator(self) -> None:
        self._orchestrator = TestOrchestrator(
            self._ip_field.text(), self._pelco_port.value(),
            self._pelco_addr.value(), self._cycles_spin.value(),
            self._stop_flag,
        )
        self._orchestrator.test_event.connect(self._on_test_event)
        self._orchestrator.cycle_updated.connect(self._on_cycle_updated)
        self._orchestrator.test_finished.connect(self._on_test_finished)
        self._orchestrator.start()

    # ── Signal Handlers ───────────────────────────────────────────────

    @pyqtSlot(str, str, object)
    def _on_ping_loss_event(self, ip: str, event_type: str, ts: object) -> None:
        tile = self._tiles.get(ip)
        if tile:
            if event_type == "Ping Loss":
                tile.set_status("Ping Loss")
                tile.increment_ping_loss()
            elif event_type == "Connectivity Loss":
                tile.set_status("Connectivity Loss")
                tile.increment_connectivity_loss()
                self._ever_connectivity_loss.add(ip)
                if self._ever_connectivity_loss.issuperset(set(self._active_devices)):
                    self._stop_flag.set()
            elif event_type == "Ping Restored":
                tile.set_status("OK")
            elif event_type == "Connectivity Restored":
                tile.set_status("Connectivity Restored")
        self._log_and_display(ip, event_type, "", ts)

    @pyqtSlot(str, str, object)
    def _on_connection_event(self, event_type: str, detail: str, ts: object) -> None:
        self._log_and_display("SSH", event_type, detail, ts)

    @pyqtSlot(str, str, object)
    def _on_test_event(self, source: str, event_type: str, ts: object) -> None:
        self._log_and_display(source, event_type, "", ts)

    @pyqtSlot(int, int)
    def _on_cycle_updated(self, current: int, total: int) -> None:
        self._status_label.setText(f"Running — Cycle {current} / {total}")

    @pyqtSlot(str)
    def _on_test_finished(self, reason: str) -> None:
        self._stop_flag.set()
        self._status_label.setText("Complete")
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(True)

    def _log_and_display(self, source: str, event_type: str,
                          detail: str, ts: object) -> None:
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.") + \
                 f"{timestamp.microsecond // 1000:03d}"
        self._logger.log(timestamp, source, event_type, detail)
        self._event_log.add_event(ts_str, source, event_type, detail)

    def closeEvent(self, event) -> None:
        self._stop_flag.set()
        self._logger.close()
        super().closeEvent(event)
