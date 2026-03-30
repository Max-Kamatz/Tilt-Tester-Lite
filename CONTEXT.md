# Tilt Tester Lite — Session Context

> This file exists so a new Claude Code session (on any machine) can pick up exactly where the last one left off. Update it at the end of each session.

**Last updated:** 2026-03-30
**Status:** Design spec and implementation plan written. No code written yet.

---

## What This Project Is

PyQt6 desktop GUI that stress-tests PTZ camera cable integrity by cycling tilt between ±90° via Pelco-D TCP, while SSH-pinging four Moxa NPort devices (10.10.10.2–10.10.10.5) via a GENE ARH6 board (Ubuntu 24.04). Packages to a single `.exe` via PyInstaller for use on a Windows operator PC.

**Full design spec:** `docs/superpowers/specs/2026-03-30-tilt-tester-lite-design.md`
**Full implementation plan:** `docs/superpowers/plans/2026-03-30-tilt-tester-lite.md`

---

## Where To Resume

**Next task: Task 1 — Project Scaffold** (first task in the implementation plan)

Steps still to do:
- [ ] Create `requirements.txt`
- [ ] Create `core/__init__.py`, `workers/__init__.py`, `ui/__init__.py`, `logger/__init__.py`, `tests/__init__.py`
- [ ] Create `tests/conftest.py` (session-scoped QApplication fixture)

Then proceed through Tasks 2–N in the plan in order.

---

## Architecture

| Component | Type | Responsibility |
|-----------|------|----------------|
| `PingMonitor` | QThread | SSH to GENE board; 4 persistent ping channels; consecutive failure counting; emits ping/connectivity events |
| `TiltController` | plain helper | Pelco-D TCP socket; speed-prime + abs tilt; blocking position poll |
| `TestOrchestrator` | QThread | Cycle loop; checks shared stop flag; emits all test events |
| `TestLogger` | plain object | Appends every event immediately to temp CSV; CSV/Excel export |
| `MainWindow` | QMainWindow | Toolbar, split layout, worker wiring, stop condition evaluation |

**Stop conditions:** (1) all 4 devices have ever hit Connectivity Loss, (2) cycle count reached, (3) user clicks Stop.

---

## Tech Stack

| | |
|---|---|
| Language | Python 3.14 |
| GUI | PyQt6 |
| SSH / remote ping | Paramiko |
| Excel export | openpyxl |
| Packaging | PyInstaller (single `.exe`) |
| Tests | pytest + pytest-qt |

---

## Key Gotchas

- `@pyqtSlot` decorator type **must exactly match** the signal's emit type — mismatch causes a silent hard crash with no useful traceback.
- Paramiko channels must be read on **background threads** — blocking reads on the Qt thread freeze the UI.
- **Speed-prime pattern:** send a continuous tilt command at max speed (0x3F) in the target direction immediately before every abs position command (0x4D). The platform ignores speed in extended position commands, so without this it may not reach ±90° within the 5 s timeout.
- Pelco-D framing is shared with `onvif-pelco-tool` — extract from `../onvif-pelco-tool/protocols/pelco_client.py` into `core/pelco_utils.py`, do not duplicate.
- PyInstaller spec must explicitly include Paramiko's vendored deps and openpyxl's `et_xmlfile`.
- `ping -i 0.2` (fast ping interval) requires the SSH user to have permission on the GENE board — standard on Ubuntu 24.04 but worth verifying.

---

## Planned File Structure

```
tilt-tester-lite/
├── main.py
├── Tilt-Tester-Lite.spec
├── requirements.txt
├── CONTEXT.md                        ← this file
├── core/
│   └── pelco_utils.py
├── workers/
│   ├── ping_monitor.py
│   ├── tilt_controller.py
│   └── test_orchestrator.py
├── ui/
│   ├── main_window.py
│   ├── device_tile.py
│   └── event_log.py
├── logger/
│   └── test_logger.py
├── tests/
│   ├── conftest.py
│   ├── test_pelco_utils.py
│   ├── test_test_logger.py
│   ├── test_ping_monitor.py
│   ├── test_tilt_controller.py
│   ├── test_orchestrator.py
│   └── test_ui.py
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-03-30-tilt-tester-lite-design.md
        └── plans/
            └── 2026-03-30-tilt-tester-lite.md
```
