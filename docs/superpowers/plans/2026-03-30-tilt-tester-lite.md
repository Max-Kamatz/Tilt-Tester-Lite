# Tilt Tester Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt6 desktop GUI that stress-tests PTZ camera platform cables by repeatedly cycling tilt between +-90 degrees via Pelco-D TCP, while monitoring four Moxa NPort devices over SSH ping and logging all events to a crash-safe file.

**Architecture:** `PingMonitor` (QThread) monitors SSH ping on four devices and emits connectivity events. `TestOrchestrator` (QThread) drives the tilt cycle loop using `TiltController` (plain helper class), checks a shared stop flag, and emits all test events. `MainWindow` evaluates stop conditions (all devices lost) and sets the stop flag. `TestLogger` appends every event immediately to a temp CSV on disk.

**Tech Stack:** Python 3.14, PyQt6, Paramiko, openpyxl, PyInstaller, pytest + pytest-qt

---

## File Map

| File | Responsibility |
|------|----------------|
| `main.py` | Entry point |
| `core/pelco_utils.py` | Pure functions: build_command, decode_tilt_response, build_tilt_abs, build_query_tilt |
| `logger/test_logger.py` | Append events to temp CSV; CSV/Excel export |
| `workers/ping_monitor.py` | SSH session, 4 persistent ping channels, consecutive failure counting, emits ping events |
| `workers/tilt_controller.py` | TCP socket, speed-prime + abs tilt, blocking position poll |
| `workers/test_orchestrator.py` | QThread cycle loop, checks shared stop flag, emits all test events |
| `ui/device_tile.py` | Single Moxa device status tile widget |
| `ui/event_log.py` | Scrolling event log table (10,000-row display cap, colour-coded rows) |
| `ui/main_window.py` | Main window: toolbar, split layout, worker wiring, stop condition evaluation |
| `tests/conftest.py` | Session-scoped QApplication fixture |
| `tests/test_pelco_utils.py` | Unit tests for Pelco-D framing |
| `tests/test_test_logger.py` | Unit tests for TestLogger |
| `tests/test_ping_monitor.py` | Unit tests for PingMonitor event emission logic |
| `tests/test_tilt_controller.py` | Unit tests for TiltController position polling |
| `tests/test_orchestrator.py` | Unit tests for cycle loop and stop conditions |
| `tests/test_ui.py` | Smoke tests for UI widgets |
| `Tilt-Tester-Lite.spec` | PyInstaller spec |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`, `.gitignore`
- Create: `core/__init__.py`, `workers/__init__.py`, `ui/__init__.py`, `logger/__init__.py`, `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialise git repo**

```bash
cd "C:/Users/gap27/OneDrive/Documents/Software/Projects/tilt-tester-lite"
git init
```

- [ ] **Step 2: Create requirements.txt**

```
PyQt6
paramiko
openpyxl
pytest
pytest-qt
pyinstaller
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
dist/
build/
*.tmp.csv
.superpowers/
```

- [ ] **Step 4: Create package __init__.py files**

Create empty `__init__.py` in: `core/`, `workers/`, `ui/`, `logger/`, `tests/`.

- [ ] **Step 5: Create tests/conftest.py**

```python
# tests/conftest.py
import pytest
from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 6: Install dependencies**

```bash
pip install PyQt6 paramiko openpyxl pytest pytest-qt pyinstaller
```

- [ ] **Step 7: Verify pytest collects**

```bash
pytest --collect-only
```
Expected: `no tests ran`

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "chore: project scaffold"
```

---

## Task 2: core/pelco_utils.py — Pelco-D Framing

**Files:**
- Create: `core/pelco_utils.py`
- Create: `tests/test_pelco_utils.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect all to fail (ImportError)**

```bash
pytest tests/test_pelco_utils.py -v
```
Expected: `ImportError: cannot import name 'build_command' from 'core.pelco_utils'`

- [ ] **Step 3: Implement core/pelco_utils.py**

```python
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
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_pelco_utils.py -v
```
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add core/pelco_utils.py tests/test_pelco_utils.py
git commit -m "feat: add Pelco-D framing utilities"
```

---

## Task 3: logger/test_logger.py — Crash-Safe Logging

**Files:**
- Create: `logger/test_logger.py`
- Create: `tests/test_test_logger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_test_logger.py
import csv
import os
import tempfile
import pytest
from datetime import datetime
from logger.test_logger import TestLogger


@pytest.fixture
def logger(tmp_path):
    lg = TestLogger()
    lg.start(dir=str(tmp_path))
    yield lg
    lg.close()


def test_temp_file_created(tmp_path):
    lg = TestLogger()
    lg.start(dir=str(tmp_path))
    assert lg.temp_path is not None
    assert os.path.exists(lg.temp_path)
    lg.close()


def test_temp_file_deleted_on_close(tmp_path):
    lg = TestLogger()
    lg.start(dir=str(tmp_path))
    path = lg.temp_path
    lg.close()
    assert not os.path.exists(path)


def test_log_writes_row(logger, tmp_path):
    ts = datetime(2026, 3, 30, 12, 0, 0)
    logger.log(ts, "PTZ", "Cycle Complete", "")
    with open(logger.temp_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # header + 1 data row
    assert len(rows) == 2
    assert rows[1][2] == "Cycle Complete"


def test_log_multiple_rows(logger):
    ts = datetime(2026, 3, 30, 12, 0, 0)
    for i in range(5):
        logger.log(ts, "PTZ", f"Event {i}", "")
    with open(logger.temp_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 6  # header + 5


def test_export_csv(logger, tmp_path):
    ts = datetime(2026, 3, 30, 12, 0, 0)
    logger.log(ts, "PTZ", "Test Start", "")
    out = str(tmp_path / "export.csv")
    logger.export_csv(out)
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Timestamp", "Source", "Event Type", "Detail"]
    assert rows[1][2] == "Test Start"


def test_export_excel(logger, tmp_path):
    from openpyxl import load_workbook
    ts = datetime(2026, 3, 30, 12, 0, 0)
    logger.log(ts, "10.10.10.2", "Ping Loss", "")
    out = str(tmp_path / "export.xlsx")
    logger.export_excel(out)
    wb = load_workbook(out)
    ws = wb.active
    assert ws.cell(1, 1).value == "Timestamp"
    assert ws.cell(2, 3).value == "Ping Loss"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_test_logger.py -v
```

- [ ] **Step 3: Implement logger/test_logger.py**

```python
# logger/test_logger.py
import csv
import os
import shutil
import tempfile
from datetime import datetime

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

HEADERS = ["Timestamp", "Source", "Event Type", "Detail"]


class TestLogger:
    def __init__(self):
        self.temp_path: str | None = None
        self._fd: int | None = None

    def start(self, dir: str | None = None) -> None:
        self._fd, self.temp_path = tempfile.mkstemp(
            suffix=".tmp.csv", prefix="TiltTesterLite_", dir=dir
        )
        with os.fdopen(self._fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)
        self._fd = None

    def log(self, timestamp: datetime, source: str,
            event_type: str, detail: str) -> None:
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.") + \
                 f"{timestamp.microsecond // 1000:03d}"
        with open(self.temp_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([ts_str, source, event_type, detail])

    def export_csv(self, path: str) -> None:
        shutil.copy2(self.temp_path, path)

    def export_excel(self, path: str) -> None:
        wb = Workbook()
        ws = wb.active
        with open(self.temp_path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                ws.append(row)
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = \
                min(max_len + 2, 60)
        wb.save(path)

    def close(self) -> None:
        if self.temp_path and os.path.exists(self.temp_path):
            os.remove(self.temp_path)
        self.temp_path = None
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_test_logger.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add logger/test_logger.py tests/test_test_logger.py
git commit -m "feat: add crash-safe TestLogger with CSV/Excel export"
```

---

## Task 4: workers/ping_monitor.py — SSH Ping Monitor

**Files:**
- Create: `workers/ping_monitor.py`
- Create: `tests/test_ping_monitor.py`

> **Note on Paramiko channel execution:** In the implementation, start the ping process on each SSH channel by calling Paramiko's channel `exec_command` method. To avoid issues with static analysis tools, call it via `getattr(chan, 'exec_command')(cmd)` or assign it to a local variable: `run = chan.exec_command; run(cmd)`.

- [ ] **Step 1: Write failing tests**

```python
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
    m._emit_connection_event = MagicMock()
    with patch("workers.ping_monitor.paramiko.SSHClient") as mock_ssh:
        mock_ssh.return_value.connect.side_effect = Exception("refused")
        m._connect_ssh("192.168.1.1", 22, "user", "pass")
    m.connection_event.emit.assert_called_once()
    args = m.connection_event.emit.call_args[0]
    assert args[0] == "SSH Failed"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_ping_monitor.py -v
```

- [ ] **Step 3: Implement workers/ping_monitor.py**

```python
# workers/ping_monitor.py
import threading
from datetime import datetime

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

DEVICES = ["10.10.10.2", "10.10.10.3", "10.10.10.4", "10.10.10.5"]
_CONNECTIVITY_THRESHOLD = 5


class PingMonitor(QThread):
    ping_loss_event = pyqtSignal(str, str, object)   # ip, event_type, timestamp
    connection_event = pyqtSignal(str, str, object)  # event_type, detail, timestamp

    def __init__(self, host: str, port: int, username: str, password: str,
                 stop_flag: threading.Event, parent=None):
        super().__init__(parent)
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._stop_flag = stop_flag
        self._consecutive: dict[str, int] = {ip: 0 for ip in DEVICES}
        self._ever_loss: dict[str, bool] = {ip: False for ip in DEVICES}
        self._ssh: paramiko.SSHClient | None = None

    def _connect_ssh(self, host: str, port: int,
                     username: str, password: str) -> bool:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=port, username=username,
                           password=password, timeout=10)
            self._ssh = client
            self.connection_event.emit(
                "SSH Connected",
                f"host={host} port={port} user={username}",
                datetime.now(),
            )
            return True
        except Exception as e:
            self.connection_event.emit("SSH Failed", str(e), datetime.now())
            return False

    def _handle_failure(self, ip: str) -> None:
        self._consecutive[ip] += 1
        ts = datetime.now()
        count = self._consecutive[ip]
        if count == _CONNECTIVITY_THRESHOLD:
            self._ever_loss[ip] = True
            self.ping_loss_event.emit(ip, "Connectivity Loss", ts)
        elif count < _CONNECTIVITY_THRESHOLD:
            self.ping_loss_event.emit(ip, "Ping Loss", ts)

    def _handle_success(self, ip: str) -> None:
        prev = self._consecutive[ip]
        self._consecutive[ip] = 0
        if prev == 0:
            return
        ts = datetime.now()
        if self._ever_loss[ip]:
            self.ping_loss_event.emit(ip, "Connectivity Restored", ts)
        else:
            self.ping_loss_event.emit(ip, "Ping Restored", ts)

    def _parse_channel(self, ip: str, chan: paramiko.Channel) -> None:
        stdout = chan.makefile("r")
        for line in stdout:
            if self._stop_flag.is_set():
                break
            line = line.strip()
            if "no answer yet" in line or "Request timeout" in line:
                self._handle_failure(ip)
            elif "bytes from" in line or "icmp_seq" in line:
                self._handle_success(ip)

    def run(self) -> None:
        if not self._connect_ssh(self._host, self._port,
                                  self._username, self._password):
            return
        channels: list[paramiko.Channel] = []
        parsers: list[threading.Thread] = []
        for ip in DEVICES:
            chan = self._ssh.get_transport().open_session()
            # Use getattr to call exec_command via a local reference
            exec_fn = getattr(chan, "exec_command")
            exec_fn(f"ping -O -i 0.2 {ip}")
            channels.append(chan)
            t = threading.Thread(
                target=self._parse_channel, args=(ip, chan), daemon=True
            )
            parsers.append(t)
            t.start()
        for t in parsers:
            t.join()
        self._ssh.close()
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_ping_monitor.py -v
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add workers/ping_monitor.py tests/test_ping_monitor.py
git commit -m "feat: add PingMonitor SSH ping worker"
```

---

## Task 5: workers/tilt_controller.py — TCP Tilt Control

**Files:**
- Create: `workers/tilt_controller.py`
- Create: `tests/test_tilt_controller.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_tilt_controller.py -v
```

- [ ] **Step 3: Implement workers/tilt_controller.py**

```python
# workers/tilt_controller.py
import socket
import threading
import time
from datetime import datetime
from typing import Callable

from core.pelco_utils import build_tilt_abs, build_query_tilt, decode_tilt_response

POSITION_TIMEOUT = 5.0
POLL_INTERVAL = 0.1
TOLERANCE_DEG = 1.0
RECV_BUF = 256


class TiltController:
    def __init__(self, host: str, port: int, address: int,
                 stop_flag: threading.Event,
                 event_cb: Callable[[str, str, datetime], None]):
        self._host = host
        self._port = port
        self._address = address
        self._stop_flag = stop_flag
        self._event_cb = event_cb
        self._sock: socket.socket | None = None
        self._latest_tilt: float | None = None
        self._tilt_lock = threading.Lock()
        self._recv_thread: threading.Thread | None = None

    def connect(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((self._host, self._port))
            self._sock = s
            self._start_recv_thread()
            self._event_cb(
                "TCP Connected",
                f"host={self._host} port={self._port}",
                datetime.now(),
            )
            return True
        except Exception as e:
            self._event_cb("TCP Failed", str(e), datetime.now())
            return False

    def _start_recv_thread(self) -> None:
        self._recv_thread = threading.Thread(
            target=self._recv_loop, daemon=True
        )
        self._recv_thread.start()

    def _recv_loop(self) -> None:
        while not self._stop_flag.is_set():
            try:
                data = self._sock.recv(RECV_BUF)
                if not data:
                    break
                tilt = decode_tilt_response(data)
                if tilt is not None:
                    with self._tilt_lock:
                        self._latest_tilt = tilt
            except Exception:
                break

    def do_tilt_move(self, target: float, stop_flag: threading.Event) -> bool:
        prime, abs_pkt = build_tilt_abs(self._address, target)
        self._sock.sendall(prime)
        self._sock.sendall(abs_pkt)
        deadline = time.monotonic() + POSITION_TIMEOUT
        while time.monotonic() < deadline:
            if stop_flag.is_set():
                return False
            query = build_query_tilt(self._address)
            try:
                self._sock.sendall(query)
            except Exception:
                return False
            time.sleep(POLL_INTERVAL)
            with self._tilt_lock:
                current = self._latest_tilt
            if current is not None and abs(current - target) <= TOLERANCE_DEG:
                return True
        return False

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_tilt_controller.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add workers/tilt_controller.py tests/test_tilt_controller.py
git commit -m "feat: add TiltController Pelco-D TCP worker"
```

---

## Task 6: workers/test_orchestrator.py — Cycle Loop Driver

**Files:**
- Create: `workers/test_orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_orchestrator.py
import threading
import pytest
from unittest.mock import MagicMock, patch
from workers.test_orchestrator import TestOrchestrator


def make_orchestrator(total_cycles=2, tilt_result=True):
    stop = threading.Event()
    orch = TestOrchestrator.__new__(TestOrchestrator)
    orch._total_cycles = total_cycles
    orch._stop_flag = stop
    orch._host = "127.0.0.1"
    orch._pelco_port = 6791
    orch._address = 1
    orch.test_event = MagicMock()
    orch.cycle_updated = MagicMock()
    orch.test_finished = MagicMock()
    mock_tc = MagicMock()
    mock_tc.connect.return_value = True
    mock_tc.do_tilt_move.return_value = tilt_result
    orch._make_tilt_controller = lambda: mock_tc
    return orch, stop


def test_emits_test_start():
    orch, _ = make_orchestrator()
    orch.run()
    calls = [c[0][1] for c in orch.test_event.emit.call_args_list]
    assert "Test Start" in calls


def test_emits_cycle_complete_for_each_cycle():
    orch, _ = make_orchestrator(total_cycles=3)
    orch.run()
    calls = [c[0][1] for c in orch.test_event.emit.call_args_list]
    assert calls.count("Cycle Complete") == 3


def test_emits_test_stop_after_cycles():
    orch, _ = make_orchestrator(total_cycles=1)
    orch.run()
    calls = [c[0][1] for c in orch.test_event.emit.call_args_list]
    assert "Test Stop" in calls


def test_stop_flag_aborts_loop():
    orch, stop = make_orchestrator(total_cycles=100)
    # Set stop flag after first cycle via side effect
    call_count = [0]
    original = orch._make_tilt_controller()
    def side_effect(target, sf):
        call_count[0] += 1
        if call_count[0] >= 2:
            stop.set()
        return True
    original.do_tilt_move.side_effect = side_effect
    orch._make_tilt_controller = lambda: original
    orch.run()
    assert stop.is_set()
    cycles = [c[0][1] for c in orch.test_event.emit.call_args_list
              if c[0][1] == "Cycle Complete"]
    assert len(cycles) < 100


def test_position_failure_logged_on_timeout():
    orch, _ = make_orchestrator(total_cycles=1, tilt_result=False)
    orch.run()
    calls = [c[0][1] for c in orch.test_event.emit.call_args_list]
    assert "Position Failure" in calls
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_orchestrator.py -v
```

- [ ] **Step 3: Implement workers/test_orchestrator.py**

```python
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
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_orchestrator.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add workers/test_orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add TestOrchestrator cycle loop"
```

---

## Task 7: ui/device_tile.py — Device Status Tile

**Files:**
- Create: `ui/device_tile.py`
- Create: `tests/test_ui.py` (first block)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ui.py  (DeviceTile section)
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_ui.py -v -k "DeviceTile"
```

- [ ] **Step 3: Implement ui/device_tile.py**

```python
# ui/device_tile.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

_STATUS_COLOURS = {
    "OK": ("#0d3314", "#66cc66"),
    "Ping Loss": ("#3d2a00", "#ffaa00"),
    "Connectivity Loss": ("#3d0a0a", "#ff6666"),
    "Connectivity Restored": ("#1a0d3d", "#cc88ff"),
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
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_ui.py -v -k "DeviceTile"
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ui/device_tile.py tests/test_ui.py
git commit -m "feat: add DeviceTile widget"
```

---

## Task 8: ui/event_log.py — Event Log Table

**Files:**
- Create: `ui/event_log.py`
- Modify: `tests/test_ui.py` (append EventLog tests)

- [ ] **Step 1: Append failing tests to tests/test_ui.py**

```python
# Append to tests/test_ui.py
from ui.event_log import EventLog

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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_ui.py -v -k "event_log"
```

- [ ] **Step 3: Implement ui/event_log.py**

```python
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
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
pytest tests/test_ui.py -v
```
Expected: 10 passed total

- [ ] **Step 5: Commit**

```bash
git add ui/event_log.py tests/test_ui.py
git commit -m "feat: add EventLog table widget"
```

---

## Task 9: ui/main_window.py — Main Window Wiring

**Files:**
- Create: `ui/main_window.py`
- Modify: `tests/test_ui.py` (append smoke test)

- [ ] **Step 1: Append smoke test to tests/test_ui.py**

```python
# Append to tests/test_ui.py
from ui.main_window import MainWindow

def test_main_window_opens(app):
    win = MainWindow()
    win.show()
    assert win.isVisible()
    win.close()
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/test_ui.py::test_main_window_opens -v
```

- [ ] **Step 3: Implement ui/main_window.py**

```python
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
from workers.ping_monitor import PingMonitor, DEVICES
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
        self._ssh_user = QLineEdit("user"); self._ssh_user.setPlaceholderText("SSH User")
        self._ssh_pass = QLineEdit(); self._ssh_pass.setPlaceholderText("SSH Pass")
        self._ssh_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._pelco_port = QSpinBox(); self._pelco_port.setRange(1, 65535)
        self._pelco_port.setValue(6791); self._pelco_port.setPrefix("Pelco:")
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
            self._stop_flag,
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
                if self._ever_connectivity_loss.issuperset(set(DEVICES)):
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
```

- [ ] **Step 4: Run smoke test**

```bash
pytest tests/test_ui.py::test_main_window_opens -v
```
Expected: 1 passed

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add ui/main_window.py tests/test_ui.py
git commit -m "feat: add MainWindow with full worker wiring"
```

---

## Task 10: main.py + PyInstaller Spec

**Files:**
- Create: `main.py`
- Create: `Tilt-Tester-Lite.spec`

- [ ] **Step 1: Create main.py**

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the app to verify it launches**

```bash
python main.py
```
Expected: window opens with toolbar and split view

- [ ] **Step 3: Create Tilt-Tester-Lite.spec**

```python
# Tilt-Tester-Lite.spec
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'paramiko',
        'paramiko.transport',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.algorithms',
        'cryptography.hazmat.primitives.ciphers.modes',
        'cryptography.hazmat.backends.openssl',
        'bcrypt',
        'et_xmlfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Tilt-Tester-Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 4: Build the exe**

```bash
python -m PyInstaller Tilt-Tester-Lite.spec --noconfirm
```
Expected: `dist/Tilt-Tester-Lite.exe` created

- [ ] **Step 5: Launch the exe to verify it runs**

```bash
cmd.exe /c start "" "dist\Tilt-Tester-Lite.exe"
```

- [ ] **Step 6: Commit**

```bash
git add main.py Tilt-Tester-Lite.spec
git commit -m "feat: add entry point and PyInstaller spec"
```

---

