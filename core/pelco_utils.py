# core/pelco_utils.py
SYNC = 0xFF
EXT_RESPONSE_TILT = 0x5B


def _checksum(body: bytes) -> int:
    return sum(body) % 256


def build_command(address: int, cmd1: int, cmd2: int,
                  data1: int = 0x00, data2: int = 0x00) -> bytes:
    body = bytes([address, cmd1, cmd2, data1, data2])
    return bytes([SYNC]) + body + bytes([_checksum(body)])


def decode_tilt_response(data: bytes) -> float | None:
    if len(data) < 7 or data[0] != SYNC:
        return None
    if data[3] != EXT_RESPONSE_TILT:
        return None
    raw = (data[4] << 8) | data[5]
    degrees = raw / 100.0
    if degrees > 180.0:
        degrees -= 360.0
    return degrees


def build_tilt_abs(address: int, tilt_degrees: float) -> tuple[bytes, bytes]:
    if tilt_degrees >= 0:
        prime = build_command(address, 0x00, 0x08, 0x00, 0x3F)  # tilt up max
    else:
        prime = build_command(address, 0x00, 0x10, 0x00, 0x3F)  # tilt down max
    tilt_raw = tilt_degrees if tilt_degrees >= 0 else 360.0 + tilt_degrees
    pos = min(int(round(tilt_raw * 100)), 35999)
    abs_pkt = build_command(address, 0x00, 0x4D, (pos >> 8) & 0xFF, pos & 0xFF)
    return prime, abs_pkt


def build_query_tilt(address: int) -> bytes:
    return build_command(address, 0x00, 0x53)
