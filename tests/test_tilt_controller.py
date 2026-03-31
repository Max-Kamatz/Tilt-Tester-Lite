# tests/test_tilt_controller.py
import socket
import threading
import pytest
from unittest.mock import MagicMock, patch
from workers.tilt_controller import TiltController


def make_controller(event_cb=None):
    stop = threading.Event()
    tc = TiltController.__new__(TiltController)
    tc._host = "127.0.0.1"
    tc._port = 6791
    tc._address = 1
    tc._stop_flag = stop
    tc._event_cb = event_cb or MagicMock()
    tc._sock = None
    tc._latest_tilt = None
    tc._tilt_lock = threading.Lock()
    return tc, stop


def test_connect_success():
    cb = MagicMock()
    tc, _ = make_controller(cb)
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        result = tc.connect()
    assert result is True
    cb.assert_called_once()
    assert cb.call_args[0][0] == "TCP Connected"


def test_connect_failure():
    cb = MagicMock()
    tc, _ = make_controller(cb)
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")
        mock_sock_cls.return_value = mock_sock
        result = tc.connect()
    assert result is False
    cb.assert_called_once()
    assert cb.call_args[0][0] == "TCP Failed"


def test_do_tilt_move_reaches_target():
    tc, stop = make_controller()
    tc._sock = MagicMock()
    # Simulate recv returning a valid tilt response at +90 degrees
    from core.pelco_utils import build_command
    resp = build_command(1, 0x00, 0x5B, 0x23, 0x28)  # 90.00 deg
    tc._sock.recv.return_value = resp
    tc._latest_tilt = 90.0
    result = tc.do_tilt_move(90.0, stop)
    assert result is True


def test_do_tilt_move_times_out():
    tc, stop = make_controller()
    tc._sock = MagicMock()
    tc._latest_tilt = 0.0   # stuck far from target
    # Use a very short timeout by monkeypatching
    with patch("workers.tilt_controller.POSITION_TIMEOUT", 0.05):
        result = tc.do_tilt_move(90.0, stop)
    assert result is False


def test_do_tilt_move_aborts_on_stop():
    tc, stop = make_controller()
    tc._sock = MagicMock()
    tc._latest_tilt = 0.0
    stop.set()
    result = tc.do_tilt_move(90.0, stop)
    assert result is False


def test_sends_speed_prime_before_abs():
    tc, stop = make_controller()
    sent = []
    tc._sock = MagicMock()
    tc._sock.sendall.side_effect = lambda b: sent.append(bytes(b))
    tc._latest_tilt = 90.0  # already at target
    with patch("workers.tilt_controller.POSITION_TIMEOUT", 1.0):
        tc.do_tilt_move(90.0, stop)
    # First packet sent should be the prime (tilt-up = cmd2 0x08)
    assert len(sent) >= 2
    assert sent[0][3] == 0x08   # CMD2 = tilt up prime
    assert sent[1][3] == 0x4D   # CMD2 = abs tilt
