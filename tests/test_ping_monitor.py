# tests/test_ping_monitor.py
import pytest
from unittest.mock import MagicMock, patch, call
from workers.ping_monitor import PingMonitor, DEVICES


def make_monitor():
    m = PingMonitor.__new__(PingMonitor)
    m._stop_flag = MagicMock()
    m._stop_flag.is_set.return_value = False
    m._consecutive = {ip: 0 for ip in DEVICES}
    m._ever_loss = {ip: False for ip in DEVICES}
    m.ping_loss_event = MagicMock()
    m.connection_event = MagicMock()
    return m


def test_devices_list():
    assert "10.10.10.2" in DEVICES
    assert len(DEVICES) == 4


def test_single_failure_emits_ping_loss():
    m = make_monitor()
    m._handle_failure("10.10.10.2")
    m.ping_loss_event.emit.assert_called_once()
    args = m.ping_loss_event.emit.call_args[0]
    assert args[0] == "10.10.10.2"
    assert args[1] == "Ping Loss"


def test_recovery_before_threshold_emits_ping_restored():
    m = make_monitor()
    m._handle_failure("10.10.10.2")  # count=1
    m._handle_success("10.10.10.2")  # recovery
    calls = [c[0][1] for c in m.ping_loss_event.emit.call_args_list]
    assert "Ping Restored" in calls


def test_fifth_failure_emits_connectivity_loss():
    m = make_monitor()
    for _ in range(5):
        m._handle_failure("10.10.10.2")
    calls = [c[0][1] for c in m.ping_loss_event.emit.call_args_list]
    assert "Connectivity Loss" in calls


def test_recovery_after_connectivity_loss_emits_connectivity_restored():
    m = make_monitor()
    for _ in range(5):
        m._handle_failure("10.10.10.2")
    m._handle_success("10.10.10.2")
    calls = [c[0][1] for c in m.ping_loss_event.emit.call_args_list]
    assert "Connectivity Restored" in calls
    assert "Ping Restored" not in calls


def test_no_ping_restored_after_connectivity_restored():
    m = make_monitor()
    for _ in range(5):
        m._handle_failure("10.10.10.2")
    m._handle_success("10.10.10.2")
    m._handle_failure("10.10.10.2")  # ping loss again
    m._handle_success("10.10.10.2")  # recovery — should NOT emit Ping Restored
    calls = [c[0][1] for c in m.ping_loss_event.emit.call_args_list]
    assert calls.count("Ping Restored") == 0


def test_consecutive_counter_resets_on_success():
    m = make_monitor()
    m._handle_failure("10.10.10.2")
    m._handle_failure("10.10.10.2")
    m._handle_success("10.10.10.2")
    assert m._consecutive["10.10.10.2"] == 0


def test_ssh_failure_emits_connection_event():
    m = make_monitor()
    with patch("workers.ping_monitor.paramiko.SSHClient") as mock_ssh:
        mock_ssh.return_value.connect.side_effect = Exception("refused")
        m._connect_ssh("192.168.1.1", 22, "user", "pass")
    m.connection_event.emit.assert_called_once()
    args = m.connection_event.emit.call_args[0]
    assert args[0] == "SSH Failed"
