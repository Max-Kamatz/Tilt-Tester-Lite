# tests/test_pelco_utils.py
import pytest
from core.pelco_utils import (
    build_command, decode_tilt_response,
    build_tilt_abs, build_query_tilt,
)

def test_build_command_length():
    pkt = build_command(1, 0x00, 0x08, 0x00, 0x3F)
    assert len(pkt) == 7

def test_build_command_sync_byte():
    pkt = build_command(1, 0x00, 0x08, 0x00, 0x3F)
    assert pkt[0] == 0xFF

def test_build_command_address():
    pkt = build_command(3, 0x00, 0x08, 0x00, 0x00)
    assert pkt[1] == 3

def test_build_command_checksum():
    # body = [1, 0, 8, 0, 0x3F] -> sum = 0x48 -> % 256 = 0x48
    pkt = build_command(1, 0x00, 0x08, 0x00, 0x3F)
    assert pkt[6] == 0x48

def test_decode_tilt_response_positive():
    # +45.00 degrees -> raw 4500 -> 0x1194
    pkt = build_command(1, 0x00, 0x5B, 0x11, 0x94)
    result = decode_tilt_response(pkt)
    assert result == pytest.approx(45.0, abs=0.01)

def test_decode_tilt_response_negative():
    # -90.00 degrees -> raw = (360 - 90)*100 = 27000 -> 0x6978
    pkt = build_command(1, 0x00, 0x5B, 0x69, 0x78)
    result = decode_tilt_response(pkt)
    assert result == pytest.approx(-90.0, abs=0.01)

def test_decode_tilt_response_zero():
    pkt = build_command(1, 0x00, 0x5B, 0x00, 0x00)
    result = decode_tilt_response(pkt)
    assert result == pytest.approx(0.0, abs=0.01)

def test_decode_tilt_response_wrong_cmd():
    pkt = build_command(1, 0x00, 0x4D, 0x11, 0x94)
    result = decode_tilt_response(pkt)
    assert result is None

def test_decode_tilt_response_short_data():
    assert decode_tilt_response(b'\xFF\x01\x00') is None

def test_decode_tilt_response_no_sync():
    assert decode_tilt_response(b'\x00\x01\x00\x5B\x00\x00\x01') is None

def test_build_tilt_abs_positive_prime():
    prime, abs_pkt = build_tilt_abs(1, 90.0)
    # prime: tilt up (cmd2=0x08), max speed data2=0x3F
    assert prime[3] == 0x08   # CMD2 = tilt up
    assert prime[5] == 0x3F   # DATA2 = max speed

def test_build_tilt_abs_negative_prime():
    prime, abs_pkt = build_tilt_abs(1, -90.0)
    # prime: tilt down (cmd2=0x10), max speed
    assert prime[3] == 0x10   # CMD2 = tilt down
    assert prime[5] == 0x3F

def test_build_tilt_abs_positive_position():
    prime, abs_pkt = build_tilt_abs(1, 90.0)
    # abs pkt CMD2 = 0x4D, position = 9000 -> 0x2328
    assert abs_pkt[3] == 0x4D
    assert abs_pkt[4] == 0x23
    assert abs_pkt[5] == 0x28

def test_build_tilt_abs_negative_position():
    prime, abs_pkt = build_tilt_abs(1, -90.0)
    # position raw = (360 - 90) * 100 = 27000 -> 0x6978
    assert abs_pkt[3] == 0x4D
    assert abs_pkt[4] == 0x69
    assert abs_pkt[5] == 0x78

def test_build_query_tilt():
    pkt = build_query_tilt(1)
    assert pkt[0] == 0xFF
    assert pkt[3] == 0x53   # query tilt cmd
    assert len(pkt) == 7
