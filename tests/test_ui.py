# tests/test_ui.py
import pytest
from PyQt6.QtWidgets import QApplication
from ui.device_tile import DeviceTile

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
