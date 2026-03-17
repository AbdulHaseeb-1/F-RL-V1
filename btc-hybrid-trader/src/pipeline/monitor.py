"""Training monitor: progress tracking, convergence detection, metric history."""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    stage: str
    fold: int = -1
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""
    duration_sec: float = 0.0
    status: str = "pending"  # pending, running, passed, failed, skipped


@dataclass
class ValidationGate:
    """Quality gate between pipeline stages."""
    metric: str
    threshold: float
    direction: str = "gte"  # gte, lte, gt, lt

    def check(self, value: float) -> bool:
        if self.direction == "gte":
            return value >= self.threshold
        elif self.direction == "lte":
            return value <= self.threshold
        elif self.direction == "gt":
            return value > self.threshold
        elif self.direction == "lt":
            return value < self.threshold
        return False


class TrainingMonitor:
    """Tracks training progress across pipeline stages with:
    - Per-stage metric recording
    - Convergence detection for iterative processes
    - Quality gates between stages
    - Full history persistence to JSON
    - Callback support for real-time reporting
    """

    def __init__(self, output_dir: str = "runs",
                 run_name: Optional[str] = None,
                 callbacks: Optional[List[Callable]] = None):
        self.run_name = run_name or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / self.run_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.history: List[StageMetrics] = []
        self.current_stage: Optional[str] = None
        self._stage_start: float = 0.0
        self._callbacks = callbacks or []

        # Convergence tracking
        self._convergence_window: Dict[str, List[float]] = {}
        self._convergence_patience = 5
        self._convergence_min_delta = 0.001

        # Validation gates
        self.gates: Dict[str, List[ValidationGate]] = {}

        logger.info("Training monitor initialized: %s", self.output_dir)

    def add_gate(self, stage: str, metric: str, threshold: float,
                 direction: str = "gte"):
        """Add quality gate to a stage."""
        if stage not in self.gates:
            self.gates[stage] = []
        self.gates[stage].append(ValidationGate(metric, threshold, direction))

    def start_stage(self, stage: str, fold: int = -1):
        """Mark a stage as started."""
        self.current_stage = stage
        self._stage_start = time.time()
        logger.info("[Monitor] Stage started: %s (fold=%d)", stage, fold)
        self._notify({"event": "stage_start", "stage": stage, "fold": fold})

    def log_metrics(self, stage: str, metrics: Dict[str, float],
                    fold: int = -1) -> StageMetrics:
        """Record metrics for a stage/fold."""
        duration = time.time() - self._stage_start if self.current_stage == stage else 0.0

        entry = StageMetrics(
            stage=stage,
            fold=fold,
            metrics=metrics,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_sec=round(duration, 2),
            status="passed",
        )
        self.history.append(entry)

        # Track convergence
        for key, val in metrics.items():
            track_key = f"{stage}.{key}"
            if track_key not in self._convergence_window:
                self._convergence_window[track_key] = []
            self._convergence_window[track_key].append(val)

        # Log
        compact = {k: round(v, 4) if isinstance(v, float) else v
                    for k, v in metrics.items()}
        logger.info("[Monitor] %s fold=%d: %s (%.1fs)",
                    stage, fold, compact, duration)
        self._notify({"event": "metrics", "stage": stage, "fold": fold,
                       "metrics": compact})

        # Auto-save
        self._save_history()
        return entry

    def check_gates(self, stage: str, metrics: Dict[str, float]) -> tuple:
        """Check all quality gates for a stage.
        Returns (passed: bool, failures: list of str)."""
        gates = self.gates.get(stage, [])
        if not gates:
            return True, []

        failures = []
        for gate in gates:
            val = metrics.get(gate.metric)
            if val is None:
                failures.append(f"{gate.metric}: missing from metrics")
                continue
            if not gate.check(val):
                failures.append(
                    f"{gate.metric}={val:.4f} failed gate "
                    f"({gate.direction} {gate.threshold})")

        passed = len(failures) == 0
        if not passed:
            logger.warning("[Monitor] Gate failures for %s: %s", stage, failures)
            self._notify({"event": "gate_failure", "stage": stage,
                           "failures": failures})
        else:
            logger.info("[Monitor] All gates passed for %s", stage)

        return passed, failures

    def is_converged(self, metric_key: str, patience: int = None,
                     min_delta: float = None) -> bool:
        """Check if a metric has converged (change within min_delta for patience steps)."""
        patience = patience or self._convergence_patience
        min_delta = min_delta or self._convergence_min_delta

        values = self._convergence_window.get(metric_key, [])
        if len(values) < patience + 1:
            return False

        recent = values[-patience:]
        # Converged if the range of recent values is within min_delta
        return (max(recent) - min(recent)) < min_delta

    def get_stage_summary(self, stage: str) -> Dict:
        """Get aggregated metrics across all folds for a stage."""
        entries = [e for e in self.history if e.stage == stage and e.status == "passed"]
        if not entries:
            return {}

        all_metrics = {}
        for entry in entries:
            for key, val in entry.metrics.items():
                if isinstance(val, (int, float)):
                    if key not in all_metrics:
                        all_metrics[key] = []
                    all_metrics[key].append(val)

        summary = {}
        for key, vals in all_metrics.items():
            arr = np.array(vals)
            summary[key] = {
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "min": float(arr.min()),
                "max": float(arr.max()),
                "last": float(arr[-1]),
                "n": len(arr),
            }
        return summary

    def get_progress(self) -> Dict:
        """Get current pipeline progress snapshot."""
        stages_seen = {}
        for entry in self.history:
            if entry.stage not in stages_seen:
                stages_seen[entry.stage] = {"count": 0, "status": "passed"}
            stages_seen[entry.stage]["count"] += 1
            if entry.status == "failed":
                stages_seen[entry.stage]["status"] = "failed"

        total_duration = sum(e.duration_sec for e in self.history)
        return {
            "run_name": self.run_name,
            "stages": stages_seen,
            "total_entries": len(self.history),
            "total_duration_sec": round(total_duration, 1),
            "current_stage": self.current_stage,
        }

    def fail_stage(self, stage: str, error: str, fold: int = -1):
        """Record a stage failure."""
        duration = time.time() - self._stage_start if self.current_stage == stage else 0.0
        entry = StageMetrics(
            stage=stage, fold=fold,
            metrics={"error": 0},
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_sec=round(duration, 2),
            status="failed",
        )
        self.history.append(entry)
        logger.error("[Monitor] Stage FAILED: %s fold=%d — %s", stage, fold, error)
        self._notify({"event": "stage_failed", "stage": stage, "error": error})
        self._save_history()

    def _save_history(self):
        """Persist full history to JSON."""
        path = self.output_dir / "training_history.json"
        data = {
            "run_name": self.run_name,
            "history": [asdict(e) for e in self.history],
            "progress": self.get_progress(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def save_summary(self):
        """Save final run summary."""
        path = self.output_dir / "run_summary.json"
        stages = set(e.stage for e in self.history)
        summary = {
            "run_name": self.run_name,
            "progress": self.get_progress(),
        }
        for stage in stages:
            summary[stage] = self.get_stage_summary(stage)

        with open(path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info("[Monitor] Summary saved to %s", path)

    def _notify(self, event: dict):
        """Call all registered callbacks."""
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.warning("Callback error: %s", e)
