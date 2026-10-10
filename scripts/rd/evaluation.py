"""Reproducible, paired comparison records for discovery runs.

The evaluator is deliberately conservative: only explicitly labelled real
runs with the same case, actor, conditions and budget can produce a delta.
Synthetic contract fixtures remain useful for testing the evaluator, but they
can never be reported as a capability improvement.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from copy import deepcopy
from typing import Any

from .core import DiscoveryError, Project

BASELINES = {"sol_direct", "v1.0.1", "v2.0"}
SOURCES = {"real", "synthetic"}


def _conditions(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DiscoveryError("Evaluation conditions must be an object")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise DiscoveryError("Evaluation conditions must be JSON-compatible") from exc


def record_run(
    project: Project, baseline: str, case_id: str, scores: dict[str, float], *,
    cost: float, actor: str, budget: float | None = None,
    conditions: dict[str, Any] | None = None, source: str = "synthetic",
) -> dict[str, Any]:
    if baseline not in BASELINES or not isinstance(case_id, str) or not case_id.strip() or not isinstance(actor, str) or not actor.strip():
        raise DiscoveryError("Evaluation run identity is invalid")
    if source not in SOURCES:
        raise DiscoveryError("Evaluation source must be real or synthetic")
    if not isinstance(scores, dict) or not scores:
        raise DiscoveryError("Evaluation scores are required")
    normalized = {}
    for metric, value in scores.items():
        if not isinstance(metric, str) or not metric or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise DiscoveryError("Scores must be finite values in [0, 1]")
        normalized[metric] = float(value)
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        raise DiscoveryError("Evaluation cost must be finite and non-negative")
    if budget is None:
        budget = cost
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget < 0:
        raise DiscoveryError("Evaluation budget must be finite and non-negative")
    result = {
        "baseline": baseline, "case_id": case_id, "scores": normalized,
        "cost": float(cost), "budget": float(budget),
        "conditions": _conditions(conditions), "actor": actor,
        "source": source, "status": "RECORDED",
    }
    project.record("evaluation_run", result)
    return result


def _source(run: dict[str, Any]) -> str:
    # Pre-source V2 records are treated as synthetic so old fixtures cannot
    # silently become scientific claims.
    return run.get("source", "synthetic")


def _pair_key(run: dict[str, Any]) -> tuple[str, str, float, str]:
    conditions = _conditions(run.get("conditions"))
    return (
        str(run.get("case_id", "")),
        json.dumps(conditions, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        float(run.get("budget", run.get("cost"))),
        str(run.get("actor", "")),
    )


def _means(runs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        for metric, value in run.get("scores", {}).items():
            grouped[run["baseline"]][metric].append(float(value))
    return {baseline: {metric: sum(values) / len(values) for metric, values in metrics.items()}
            for baseline, metrics in grouped.items()}


def compare_runs(project: Project) -> dict[str, Any]:
    runs = [event["payload"] for event in project.events() if event["kind"] == "evaluation_run"]
    if not runs:
        return {"status": "ERROR", "error": "no evaluation runs", "metrics": {}, "cost": {}}
    means = _means(runs)
    costs: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        costs[run["baseline"]].append(float(run.get("cost", 0)))

    # Pair only explicitly real records. The key includes task/case, actor,
    # frozen conditions and allocated budget.
    real_groups: dict[tuple[str, str, float, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    synthetic_groups: dict[tuple[str, str, float, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        target = real_groups if _source(run) == "real" else synthetic_groups
        target[_pair_key(run)][run["baseline"]].append(run)

    paired: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for key, by_baseline in real_groups.items():
        if len(by_baseline.get("v1.0.1", [])) == 1 and len(by_baseline.get("v2.0", [])) == 1:
            v1, v2 = by_baseline["v1.0.1"][0], by_baseline["v2.0"][0]
            paired.append({"case_id": key[0], "conditions": v1.get("conditions", {}),
                           "budget": key[2], "actor": key[3], "v1_run": v1, "v2_run": v2})
        else:
            ambiguous.append({"case_id": key[0], "conditions": key[1], "budget": key[2],
                              "actor": key[3], "baselines": {name: len(values) for name, values in by_baseline.items()}})

    metrics: dict[str, Any] = {}
    metric_names = sorted({metric for pair in paired for name in ("v1_run", "v2_run") for metric in pair[name].get("scores", {})})
    for metric in metric_names:
        complete = [pair for pair in paired if metric in pair["v1_run"].get("scores", {}) and metric in pair["v2_run"].get("scores", {})]
        deltas = [pair["v2_run"]["scores"][metric] - pair["v1_run"]["scores"][metric] for pair in complete]
        metrics[metric] = {
            "paired_count": len(deltas),
            "v1.0.1": sum(pair["v1_run"]["scores"][metric] for pair in complete) / len(complete) if complete else None,
            "v2.0": sum(pair["v2_run"]["scores"][metric] for pair in complete) / len(complete) if complete else None,
            "delta_v2_vs_v1": round(sum(deltas) / len(deltas), 10) if deltas else None,
        }

    synthetic_count = sum(1 for by_baseline in synthetic_groups.values()
                          if len(by_baseline.get("v1.0.1", [])) == 1 and len(by_baseline.get("v2.0", [])) == 1)
    return {
        "status": "PASS", "run_count": len(runs), "baselines": sorted(means),
        "means": means,
        "means_by_source": {source: _means([run for run in runs if _source(run) == source]) for source in sorted(SOURCES)},
        "metrics": metrics,
        "cost": {key: round(sum(values) / len(values), 10) for key, values in costs.items()},
        "pairing": {"real_pairs": len(paired), "ambiguous_or_unpaired_real": len(ambiguous),
                    "synthetic_matching_pairs": synthetic_count, "synthetic_deltas_blocked": True,
                    "key_fields": ["case_id", "actor", "conditions", "budget"]},
        "paired_comparisons": [{"case_id": item["case_id"], "conditions": deepcopy(item["conditions"]),
                                "budget": item["budget"], "actor": item["actor"]} for item in paired],
        "unpaired_real": ambiguous,
        "limitations": [
            "Only explicitly labelled real runs with identical case, actor, conditions and budget produce deltas.",
            "Synthetic fixtures are reported for contract coverage and cannot establish a scientific capability improvement.",
            "A paired delta is descriptive and does not establish scientific superiority without an independent holdout suite.",
        ],
    }
