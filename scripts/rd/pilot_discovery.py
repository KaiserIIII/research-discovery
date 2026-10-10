"""Safe, non-executing source-analysis pilot for computer-science discovery."""
from __future__ import annotations

import ast
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

from .core import DiscoveryError, Project, contained, digest, sha, write_json
from .limits import run_bounded

_REQUIRED = {"id", "candidate_id", "stage", "source_evidence", "metrics", "controls",
             "limits", "seed", "stop_rule", "predictions"}
_METRICS = {"lines", "functions", "classes", "imports", "branches", "try_blocks", "todo_markers"}


def _frozen(protocol: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(protocol)
    value.pop("registration_sha256", None)
    return value


def _validate(protocol: dict[str, Any], project: Project) -> tuple[dict[str, Any], Any]:
    if not isinstance(protocol, dict) or not _REQUIRED.issubset(protocol):
        raise DiscoveryError("Static analysis protocol is missing required fields")
    if protocol.get("stage") != "PILOT" or not isinstance(protocol.get("metrics"), list) or not protocol["metrics"]:
        raise DiscoveryError("Static analysis protocol must be a PILOT with metrics")
    if any(metric not in _METRICS for metric in protocol["metrics"]):
        raise DiscoveryError("Unknown static analysis metric")
    if not isinstance(protocol.get("seed"), int) or isinstance(protocol.get("seed"), bool):
        raise DiscoveryError("Static analysis seed must be an integer")
    entry = project.evidence().get(protocol["source_evidence"])
    if not entry or entry.get("kind") not in {"source_code", "text", "fulltext", "public_primary_source"}:
        raise DiscoveryError("Static analysis source evidence is missing or not source text")
    path = contained(project.root, entry["path"])
    if not path.is_file():
        raise DiscoveryError("Static analysis source is missing on disk")
    if sha(path) != entry.get("sha256"):
        raise DiscoveryError("Static analysis source evidence was tampered")
    limits = protocol["limits"]
    if not isinstance(limits, dict) or any(key not in limits for key in ("seconds", "memory_mb", "disk_mb", "cpu_seconds")):
        raise DiscoveryError("Static analysis limits are incomplete")
    for key, config_key in (("seconds", "total_seconds"), ("memory_mb", "max_memory_mb"),
                            ("disk_mb", "max_disk_mb"), ("cpu_seconds", "max_cpu_seconds")):
        value = limits[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0 or value > project.config[config_key]:
            raise DiscoveryError("Static analysis limit exceeds project budget: " + key)
    return entry, path


def preregister_static_analysis(project: Project, protocol: dict[str, Any]) -> dict[str, Any]:
    _validate(protocol, project)
    if project.audit():
        raise DiscoveryError("Cannot preregister while evidence is tampered")
    frozen = _frozen(protocol)
    registration_sha256 = digest(frozen)
    if any(event["kind"] == "static_analysis_registered" and event["payload"].get("protocol_sha256") == registration_sha256
           for event in project.events()):
        raise DiscoveryError("Static analysis protocol is already registered")
    project.freeze("static_analysis_protocol", frozen)
    project.record("static_analysis_registered", {"protocol_sha256": registration_sha256,
                                                   "protocol_id": protocol["id"],
                                                   "source_evidence": protocol["source_evidence"]})
    result = copy.deepcopy(frozen)
    result["registration_sha256"] = registration_sha256
    return result


def _measure(text: str) -> dict[str, int]:
    lines = len(text.splitlines())
    todo_markers = sum(text.lower().count(marker) for marker in ("todo", "fixme"))
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"lines": lines, "functions": 0, "classes": 0, "imports": 0, "branches": 0,
                "try_blocks": 0, "todo_markers": todo_markers, "syntax_error": 1, "syntax_error_line": exc.lineno or 0}
    return {
        "lines": lines,
        "functions": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
        "imports": sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)),
        "branches": sum(isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.Match)) for node in ast.walk(tree)),
        "try_blocks": sum(isinstance(node, ast.Try) for node in ast.walk(tree)),
        "todo_markers": todo_markers,
        "syntax_error": 0,
    }


def run_static_analysis(project: Project, protocol: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(protocol, dict) or not protocol.get("registration_sha256"):
        raise DiscoveryError("Static analysis must be preregistered")
    registration_sha = protocol["registration_sha256"]
    if digest(_frozen(protocol)) != registration_sha:
        raise DiscoveryError("Registered static analysis protocol was modified")
    if not any(event["kind"] == "static_analysis_registered" and event["payload"].get("protocol_sha256") == registration_sha
               for event in project.events()):
        raise DiscoveryError("Unknown static analysis registration")
    if any(event["kind"] == "static_analysis_result" and event["payload"].get("protocol_sha256") == registration_sha
           for event in project.events()):
        raise DiscoveryError("Static analysis registration has already run")
    entry, path = _validate(protocol, project)
    project.consume("max_pilots", 1)
    run_root = project.root / "runs" / ("ast-" + registration_sha)
    run_root.mkdir(parents=True, exist_ok=True)
    runtime = {"source_path": str(path), "metrics": protocol["metrics"]}
    protocol_path = run_root / "protocol.json"
    write_json(protocol_path, runtime)
    worker = str(Path(__file__).with_name("ast_worker.py"))
    started = time.monotonic()
    bounded = run_bounded([sys.executable, "-I", worker, str(protocol_path)], run_root, protocol["limits"])
    elapsed = max(time.monotonic() - started, bounded.get("elapsed_seconds", 0.0))
    try:
        project.consume("total_seconds", min(elapsed, project.remaining("total_seconds")))
    except DiscoveryError:
        pass
    stdout_path, stderr_path = (Path(bounded["stdout_path"]), Path(bounded["stderr_path"]))
    output_evidence = project.add_evidence(stdout_path, "AST pilot worker stdout", "pilot_output")
    stderr_evidence = None
    if stderr_path.stat().st_size or bounded["returncode"] not in (0, None) or bounded.get("stop_reason"):
        stderr_evidence = project.add_evidence(stderr_path, "AST pilot worker stderr", "pilot_stderr")
    result = {"status": "STOPPED" if bounded.get("stop_reason") else ("COMPLETED" if bounded["returncode"] == 0 else "FAILED"),
              "interpretation": "INCONCLUSIVE", "measurement": {}, "all_metrics": {},
              "output_evidence": output_evidence, "stderr_evidence": stderr_evidence,
              "protocol_sha256": registration_sha,
              "candidate_id": protocol["candidate_id"], "elapsed_seconds": elapsed,
              "execution_mode": "AST_PARSE_ONLY_BOUNDED", "scientific_status": "EXPLORATORY_ONLY",
              "stop_reason": bounded.get("stop_reason"),
              "limitations": ["Static structure is an observation, not semantic correctness, a causal effect, or support for a scientific hypothesis."]}
    if result["status"] == "COMPLETED":
        try:
            payload = json.loads(stdout_path.read_text(encoding="utf-8"))
            if payload.get("status") != "COMPLETED":
                raise ValueError(payload.get("error", "AST worker failed"))
            measurement = payload["measurement"]
            result["all_metrics"] = measurement
            result["measurement"] = {key: measurement[key] for key in protocol["metrics"]}
            if measurement.get("syntax_error"):
                result["interpretation"] = "FAILED"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["status"] = "FAILED"
            result["error"] = str(exc)
            result["stderr_evidence"] = stderr_evidence or project.add_evidence(stderr_path, "AST pilot parse failure", "pilot_stderr")
    project.record("static_analysis_result", result)
    return result
