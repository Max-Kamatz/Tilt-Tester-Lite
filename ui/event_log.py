# ui/event_log.py
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QHeaderView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

_ROW_COLOURS = {
    "Ping Loss": "#3d2a00",
    "Ping Restored": "#0d3314",
    "Connectivity Loss": "#3d0a0a",
    "Connectivity Restored": "#0d3314",
    "Position Reached": "#1c2333",
    "Position Failure": "#3d0a0a",
    "Cycle Complete": "#1c2333",
    "SSH Connected": "#002244",
    "SSH Failed": "#3d0a0a",
    "TCP Connected": "#002244",
    "TCP Failed": "#3d0a0a",
    "Test Start": "#002244",
    "Test Stop": "#002244",
}
_DEFAULT_COLOUR = "#1c2333"
_MAX_ROWS = 10_000
_HEADERS = ["Timestamp", "Source", "Event Type", "Detail"]


class EventLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        ctrl = QHBoxLayout()
        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)
        ctrl.addWidget(self._auto_scroll)
        ctrl.addStretch()
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._table.verticalHeader().setVisible(False)
        layout.addLayout(ctrl)
        layout.addWidget(self._table)

    def add_event(self, timestamp: str, source: str,
                  event_type: str, detail: str) -> None:
        if self._table.rowCount() >= _MAX_ROWS:
            self._table.removeRow(0)
        row = self._table.rowCount()
        self._table.insertRow(row)
        bg = QColor(_ROW_COLOURS.get(event_type, _DEFAULT_COLOUR))
        for col, text in enumerate([timestamp, source, event_type, detail]):
            item = QTableWidgetItem(text)
            item.setBackground(bg)
            self._table.setItem(row, col, item)
        if self._auto_scroll.isChecked():
            self._table.scrollToBottom()

    def clear(self) -> None:
        self._table.setRowCount(0)
