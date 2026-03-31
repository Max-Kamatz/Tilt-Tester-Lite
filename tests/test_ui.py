# tests/test_ui.py
import pytest
from PyQt6.QtWidgets import QApplication
from ui.device_tile import DeviceTile
from ui.event_log import EventLog

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_device_tile_ip_label(app):
    tile = DeviceTile("10.10.10.2")
    assert "10.10.10.2" in tile._ip_label.text()


def test_device_tile_initial_status_ok(app):
    tile = DeviceTile("10.10.10.2")
    assert tile._status == "OK"


def test_device_tile_set_status_ping_loss(app):
    tile = DeviceTile("10.10.10.2")
    tile.set_status("Ping Loss")
    assert tile._status == "Ping Loss"


def test_device_tile_set_status_connectivity_loss(app):
    tile = DeviceTile("10.10.10.2")
    tile.set_status("Connectivity Loss")
    assert tile._status == "Connectivity Loss"


def test_device_tile_increment_ping_loss(app):
    tile = DeviceTile("10.10.10.2")
    tile.increment_ping_loss()
    tile.increment_ping_loss()
    assert tile._ping_loss_count == 2


def test_device_tile_reset(app):
    tile = DeviceTile("10.10.10.2")
    tile.set_status("Ping Loss")
    tile.increment_ping_loss()
    tile.reset()
    assert tile._status == "OK"
    assert tile._ping_loss_count == 0
    assert tile._connectivity_loss_count == 0


def test_device_tile_increment_connectivity_loss(app):
    tile = DeviceTile("10.10.10.2")
    tile.increment_connectivity_loss()
    tile.increment_connectivity_loss()
    assert tile._connectivity_loss_count == 2


_ROW_DATA = ("2026-03-30 12:00:00.000", "PTZ", "Cycle Complete", "")

def test_event_log_adds_row(app):
    log = EventLog()
    log.add_event(*_ROW_DATA)
    assert log._table.rowCount() == 1


def test_event_log_cap_at_10000(app):
    log = EventLog()
    for i in range(10_001):
        log.add_event(f"ts_{i}", "PTZ", "Cycle Complete", "")
    assert log._table.rowCount() == 10_000


def test_event_log_colour_coded_row(app):
    log = EventLog()
    log.add_event("ts", "10.10.10.2", "Ping Loss", "")
    item = log._table.item(0, 0)
    assert item.background().color().name() == "#3d2a00"


def test_event_log_clear(app):
    log = EventLog()
    log.add_event(*_ROW_DATA)
    log.clear()
    assert log._table.rowCount() == 0
