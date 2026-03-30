# Tilt Tester Lite — Design Spec
**Date:** 2026-03-30
**Author:** Glenn (R&D Systems Engineering)
**Status:** Approved

---

## Overview

Tilt Tester Lite is a PyQt6 desktop GUI that performs a mechanical cable stress test on a PTZ camera platform. It drives the platform between tilt extremes (−90° and +90°) repeatedly via Pelco-D TCP, whilst monitoring connectivity of four Moxa NPort serial-IP devices via SSH ping. The purpose is to detect whether network cables fail under repeated extremes of movement.

The target platform is a GENE ARH6 board running Ubuntu 24.04. The Moxa NPort devices sit on a private subnet (10.10.10.2–10.10.10.5) accessible only via the GENE board; pinging is therefore performed on the GENE board over SSH.

---

## Stack

| Component | Library |
|---|---|
| GUI | PyQt6 |
| SSH / remote ping | Paramiko |
| Excel export | openpyxl |
| Packaging | PyInstaller (single `.exe`, runs on Windows operator PC) |
| Pelco-D framing | Shared utility extracted from `onvif-pelco-tool` |

---

## UI Layout

Single window, dark theme (`#0d1117` background, `#3277ff` accent) consistent with the ONVIF/Pelco-D tool.

### Top Toolbar (fixed height)

**Connection group:**
- IP address field (shared by SSH and Pelco-D)
- SSH port spinbox (default: 22)
- SSH username field
- SSH password field (masked)
- Pelco-D port spinbox (default: 6791)
- Pelco-D address spinbox (default: 1, range 1–255)

**Test group:**
- Cycle count spinbox (number of full −90°→+90° cycles)
- Start button
- Stop button (enabled during test)
- Export button (enabled once test has started)
- Status label: `Idle` / `Running — Cycle N / M` / `Stopped` / `Complete`

### Bottom Split (resizable)

**Left — Device Status Panel:**
Four fixed tiles, one per Moxa NPort device (10.10.10.2–10.10.10.5). Each tile displays:
- IP address
- Status badge: `OK` (green) / `Ping Loss` (amber) / `Connectivity Loss` (red)
- Ping loss count (this test)
- Connectivity loss count (this test)

**Right — Event Log:**
Scrolling table, auto-scroll checkbox (default on). Displays the last 10,000 events; older rows are dropped from the display but fully preserved in the temp log file. Columns:

| Column | Content |
|---|---|
| Timestamp | `YYYY-MM-DD HH:MM:SS.mmm` |
| Source | Device IP or `PTZ` |
| Event Type | See Event Definitions |
| Detail | e.g. tilt value, consecutive loss count |

Rows are colour-coded by event type (see Event Definitions).

---

## Architecture

Three QThread workers communicate to the main window via Qt signals. A non-threaded `TestLogger` accumulates all events.

```
MainWindow
├── PingMonitor        (QThread) — SSH ping, emits ping_result signals
├── TiltController     (QThread) — Pelco-D TCP, drives tilt state machine, emits tilt_event signals
├── TestOrchestrator   (QThread) — cycle counter, stop logic, coordinates workers
└── TestLogger         (object)  — event accumulation, CSV/Excel export
```

### PingMonitor

- On start, attempts SSH connection to the GENE board. Emits `SSH Connected` (Detail: host, port, username) or `SSH Failed` (Detail: error message). If `SSH Failed`, signals the orchestrator to abort — the test does not proceed.
- Opens one Paramiko SSH session to the GENE board.
- Spawns 4 persistent SSH exec channels, each running:
  `ping -i 0.2 10.10.10.X`
- Four background threads parse each channel's stdout stream.
- **Owns consecutive-failure counters per device.** Emits `ping_result(ip, success, timestamp)` for every ping, and emits the higher-level `ping_loss_event(ip, event_type, timestamp)` when thresholds are crossed.
- **Event emission rules:**
  - Single failure → emit `Ping Loss`
  - Ping recovers after `Ping Loss` (before reaching 5) → emit `Ping Restored`
  - 5th consecutive failure → emit `Connectivity Loss`
  - Ping recovers after `Connectivity Loss` → emit `Connectivity Restored` (not `Ping Restored`)
- **Device status badge transitions:** `OK` → `Ping Loss` (1 failure) → `Connectivity Loss` (5 consecutive) → `Connectivity Restored` (recovery after connectivity loss). `Connectivity Restored` does not reset to `OK` — the badge is permanent for the remainder of the test.
- The QThread owns the SSH session. The 4 per-channel stdout parsers are plain Python `threading.Thread` objects (not additional QThreads) started within the worker's `run()` method.

### TiltController

- On start, attempts to open a Pelco-D TCP socket to `{IP}:{pelco_port}`. Emits `TCP Connected` or `TCP Failed` event. If `TCP Failed`, signals the orchestrator to abort — the test does not proceed.
- Opens a Pelco-D TCP socket to `{IP}:{pelco_port}`.
- Uses `absolute_move()` and `query_tilt()` logic (shared Pelco-D utility).
- Drives the tilt state machine (see below).
- Emits `tilt_event(type: str, value: float, timestamp: datetime)`.

### TestOrchestrator

- Owns the cycle counter.
- Listens to `ping_loss_event` and `tilt_event` signals.
- Evaluates stop conditions after each event.
- Signals the main window to update UI state.

### TestLogger

- At test start, opens a temp CSV file (e.g. `%TEMP%\TiltTesterLite_<timestamp>.tmp.csv`) for append-write.
- Every event is written to the temp file immediately as it occurs — this bounds memory usage and protects against data loss if the app crashes mid-run.
- On Export: opens `QFileDialog.getSaveFileName()` pre-populated with `TiltTesterLite_YYYYMMDD_HHMMSS`, user selects location and format.
- Export reads from the temp file (not from memory), so a 48-hour run exports fully regardless of UI display limits.
- Writes CSV (stdlib `csv`) or Excel (openpyxl with auto-filter on all columns).
- Temp file is deleted on clean application exit; survives a crash so data is recoverable.

---

## Test State Machine

```
IDLE
  └─ [Start] ──► RUNNING
                   └─ TILT_TO_NEGATIVE  (send abs tilt −90°)
                        └─ AWAIT_NEGATIVE  (poll position, ±1°, 5s timeout)
                             ├─ timeout  ──► log Position Failure, continue to DWELL
                             └─ confirmed ─► DWELL (0.5s)
                                              └─ TILT_TO_POSITIVE  (send abs tilt +90°)
                                                   └─ AWAIT_POSITIVE  (poll position, ±1°, 5s timeout)
                                                        ├─ timeout  ──► log Position Failure, continue to DWELL
                                                        └─ confirmed ─► DWELL (0.5s)
                                                                          └─ CYCLE_COMPLETE
                                                                               └─ [repeat or stop]
STOPPED  ◄── any stop condition met
```

**Stop conditions** (evaluated after every event):
1. All 4 devices have ever reached `Connectivity Loss` (i.e. current badge is `Connectivity Loss` or `Connectivity Restored`) → stop, log reason. A device that recovers to `Connectivity Restored` still counts toward this condition.
2. Cycle count reached → stop, log reason
3. User clicks Stop → stop immediately, mid-cycle

---

## Event Definitions

| Event Type | Trigger | Row Colour |
|---|---|---|
| `Ping Loss` | Single failed ping on any device | Amber `#3d2a00` |
| `Ping Restored` | Ping recovers after a loss | Green `#0d3314` |
| `Connectivity Loss` | 5 consecutive ping failures | Red `#3d0a0a` |
| `Connectivity Restored` | Ping recovers after connectivity loss | Green `#0d3314` |
| `Position Reached` | Tilt within ±1° of target | Neutral `#1c2333` |
| `Position Failure` | Tilt not within ±1° after 5s | Red `#3d0a0a` |
| `Cycle Complete` | Both tilt targets confirmed | Neutral `#1c2333` |
| `SSH Connected` | SSH session established successfully (Detail: host, port, user) | Blue `#002244` |
| `SSH Failed` | SSH connection attempt failed (Detail: error message) | Red `#3d0a0a` |
| `TCP Connected` | Pelco-D TCP socket connected successfully (Detail: host, port) | Blue `#002244` |
| `TCP Failed` | Pelco-D TCP connection attempt failed (Detail: error message) | Red `#3d0a0a` |
| `Test Start` | Test begins | Blue `#002244` |
| `Test Stop` | Test ends (with reason in Detail) | Blue `#002244` |

---

## Pelco-D Integration

The tilt command and position query logic is extracted from `onvif-pelco-tool/protocols/pelco_client.py` into a shared utility module:

- `build_command(address, cmd1, cmd2, data1, data2) → bytes`
- `decode_position_response(data) → (axis, degrees) | None`

Only the tilt axis is used. The Pelco-D address is set via the toolbar spinbox (default: 1).

### Speed Priming

Abs tilt commands (0x4D) carry only a position, not a speed. To ensure the platform moves at maximum speed and reaches ±90° within the 5-second timeout, the `TiltController` shall send a **continuous tilt command at maximum speed (0x3F)** in the target direction immediately before each abs position command:

```
[continuous tilt up/down @ 0x3F]  →  [abs tilt 0x4D to ±90°]
```

The continuous command primes the platform speed; the abs command sets the target. This is a known pattern for Pelco-D platforms that do not carry a speed byte in the extended position command.

---

## Export

- **Trigger:** Export button → `QFileDialog.getSaveFileName()` with filter `"CSV (*.csv);;Excel (*.xlsx)"`, pre-populated filename `TiltTesterLite_YYYYMMDD_HHMMSS`.
- **CSV:** One row per event, UTF-8, headers: `Timestamp, Source, Event Type, Detail`.
- **Excel:** Same data, `openpyxl`, auto-filter enabled on all columns, column widths auto-sized.
- **Availability:** Export enabled as soon as the test starts; remains enabled after stop (allows exporting a partial run).

---

## File Structure

```
tilt-tester-lite/
├── main.py
├── Tilt-Tester-Lite.spec         # PyInstaller spec
├── core/
│   └── pelco_utils.py            # Shared Pelco-D framing utilities
├── workers/
│   ├── ping_monitor.py           # SSH ping worker (QThread)
│   ├── tilt_controller.py        # Pelco-D tilt state machine (QThread)
│   └── test_orchestrator.py      # Cycle/stop logic (QThread)
├── ui/
│   ├── main_window.py            # Main window, toolbar, split layout
│   ├── device_tile.py            # Single device status tile widget
│   └── event_log.py              # Event log table widget
├── logger/
│   └── test_logger.py            # Event accumulation, CSV/Excel export
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-03-30-tilt-tester-lite-design.md
```

---

## Key Constraints & Gotchas

- `@pyqtSlot` decorator type must exactly match the signal's type — mismatch causes a silent hard crash.
- Paramiko channels must be read on background threads; blocking reads on the Qt thread will freeze the UI.
- `ping -i 0.2` requires the SSH user to have permission to run ping on the GENE board (standard on Ubuntu 24.04).
- Position polling sends `query_tilt` Pelco-D commands; the receive socket must be open and listening before polling begins.
- PyInstaller spec must include Paramiko's vendored dependencies and openpyxl's `et_xmlfile` dependency.
