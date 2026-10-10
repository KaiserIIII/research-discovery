"""Reproducible comparison records for direct, V1 and V2 discovery runs."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .core import DiscoveryError, Project

BASELINES = {"sol_direct", "v1.0.1", "v2.0"}


def record_run(project: Project, baseline: str, case_id: str, scores: dict[str, float], *, cost: float, actor: str) -> dict[str, Any]:
    if baseline not in BASELINES or not isinstance(case_id, str) or not case_id.strip() or not isinstance(actor, str) or not actor.strip():
        raise DiscoveryError("Evaluation run identity is invalid")
    if not isinstance(scores, dict) or not scores:
        raise DiscoveryError("Evaluation scores are required")
    normalized = {}
    for metric, value in scores.items():
        if not isinstance(metric, str) or not metric or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise DiscoveryError("Scores must be finite values in [0, 1]")
        normalized[metric] = float(value)
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        raise DiscoveryError("Evaluation cost must be finite and non-negative")
    result = {"baseline": baseline, "case_id": case_id, "scores": normalized, "cost": float(cost),
              "actor": actor, "status": "RECORDED"}
    project.record("evaluation_run", result)
    return result


def compare_runs(project: Project) -> dict[str, Any]:
    runs = [event["payload"] for event in project.events() if event["kind"] == "evaluation_run"]
    if not runs:
        return {"status": "ERROR", "error": "no evaluation runs", "metrics": {}, "cost": {}}
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    costs: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for metric, value in run["scores"].items():
            grouped[run["baseline"]][metric].append(float(value))
        costs[run["baseline"]].append(float(run["cost"]))
    means = {baseline: {metric: sum(values) / len(values) for metric, values in metrics.items()}
             for baseline, metrics in grouped.items()}
    metrics: dict[str, Any] = {}
    v1 = means.get("v1.0.1", {})
    v2 = means.get("v2.0", {})
    for metric in sorted(set(v1) | set(v2)):
        metrics[metric] = {"v1.0.1": v1.get(metric), "v2.0": v2.get(metric),
                           "delta_v2_vs_v1": None if metric not in v1 or metric not in v2 else round(v2[metric] - v1[metric], 10)}
    return {"status": "PASS", "run_count": len(runs), "baselines": sorted(means), "means": means,
            "metrics": metrics, "cost": {key: round(sum(values) / len(values), 10) for key, values in costs.items()},
            "limitations": ["This comparison is descriptive; it does not establish scientific superiority without an independent holdout suite."]}
