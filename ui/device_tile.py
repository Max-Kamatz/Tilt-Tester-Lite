# ui/device_tile.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

_STATUS_COLOURS = {
    "OK": ("#0d3314", "#66cc66"),
    "Ping Loss": ("#3d2a00", "#ffaa00"),
    "Connectivity Loss": ("#3d0a0a", "#ff6666"),
    "Connectivity Restored": ("#1a0d3d", "#cc88ff"),
    "Not Present": ("#161b22", "#555e6b"),
}


class DeviceTile(QFrame):
    def __init__(self, ip: str, parent=None):
        super().__init__(parent)
        self._ip = ip
        self._status = "OK"
        self._ping_loss_count = 0
        self._connectivity_loss_count = 0
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._ip_label = QLabel(self._ip)
        self._ip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge = QLabel()
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_label = QLabel()
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._ip_label)
        layout.addWidget(self._badge)
        layout.addWidget(self._stats_label)

    def _refresh(self) -> None:
        bg, fg = _STATUS_COLOURS.get(self._status, ("#1c2333", "#c9d1d9"))
        self.setStyleSheet(
            f"DeviceTile {{ background:{bg}; border-radius:4px; }}"
        )
        self._badge.setText(self._status)
        self._badge.setStyleSheet(f"color:{fg}; font-weight:bold;")
        self._stats_label.setText(
            f"PL: {self._ping_loss_count}  CL: {self._connectivity_loss_count}"
        )

    def set_status(self, status: str) -> None:
        self._status = status
        self._refresh()

    def increment_ping_loss(self) -> None:
        self._ping_loss_count += 1
        self._refresh()

    def increment_connectivity_loss(self) -> None:
        self._connectivity_loss_count += 1
        self._refresh()

    def reset(self) -> None:
        self._status = "OK"
        self._ping_loss_count = 0
        self._connectivity_loss_count = 0
        self._refresh()
