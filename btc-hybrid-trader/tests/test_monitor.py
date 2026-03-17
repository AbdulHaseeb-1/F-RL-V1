"""Tests for training monitor."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from pipeline.monitor import TrainingMonitor
from pipeline.monitor import ValidationGate


def test_monitor_logs_metrics(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.start_stage("xgb_fold")
    entry = mon.log_metrics("xgb_fold", {"win_rate": 0.55, "n_trades": 100}, fold=0)
    assert entry.status == "passed"
    assert entry.metrics["win_rate"] == 0.55


def test_monitor_gate_pass(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.add_gate("eval", "win_rate", 0.5, "gte")
    passed, failures = mon.check_gates("eval", {"win_rate": 0.55})
    assert passed is True
    assert len(failures) == 0


def test_monitor_gate_fail(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.add_gate("eval", "win_rate", 0.6, "gte")
    passed, failures = mon.check_gates("eval", {"win_rate": 0.55})
    assert passed is False
    assert len(failures) == 1


def test_monitor_convergence(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    # Not converged - values still improving
    for i in range(10):
        mon.log_metrics("train", {"loss": 1.0 - i * 0.1}, fold=i)
    assert not mon.is_converged("train.loss", patience=3)

    # Converged - values plateau
    for i in range(10):
        mon.log_metrics("train", {"loss": 0.5}, fold=10 + i)
    assert mon.is_converged("train.loss", patience=3, min_delta=0.001)


def test_monitor_stage_summary(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.log_metrics("xgb", {"wr": 0.50}, fold=0)
    mon.log_metrics("xgb", {"wr": 0.55}, fold=1)
    mon.log_metrics("xgb", {"wr": 0.60}, fold=2)
    summary = mon.get_stage_summary("xgb")
    assert summary["wr"]["mean"] == pytest.approx(0.55, abs=0.01)
    assert summary["wr"]["max"] == pytest.approx(0.60, abs=0.01)


def test_monitor_saves_history(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.log_metrics("stage1", {"val": 1.0})
    path = tmp_path / "test_run" / "training_history.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["run_name"] == "test_run"
    assert len(data["history"]) == 1


def test_monitor_progress(tmp_path):
    mon = TrainingMonitor(output_dir=str(tmp_path), run_name="test_run")
    mon.log_metrics("a", {"x": 1.0})
    mon.log_metrics("b", {"y": 2.0})
    progress = mon.get_progress()
    assert "a" in progress["stages"]
    assert "b" in progress["stages"]
    assert progress["total_entries"] == 2
