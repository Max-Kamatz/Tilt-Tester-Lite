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
