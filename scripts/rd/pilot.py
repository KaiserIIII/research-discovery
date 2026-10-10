"""Preregistered, built-in CSV pilots with immutable evidence and budgets."""
from __future__ import annotations

import copy
import json
import math
import sys
import time
from pathlib import Path

from .core import DiscoveryError, Project, canonical, digest, read_json, write_json
from .limits import run_bounded


_METHODS = {"group_difference", "paired_difference"}
_REQUIRED = {"id", "candidate_id", "stage", "hypothesis", "rivals", "data_evidence",
             "method", "parameters", "primary_observable", "variables", "controls",
             "sources", "stop_rule", "predictions", "limits", "seed"}


def _frozen_protocol(protocol):
    value = copy.deepcopy(protocol)
    value.pop("registration_sha256", None)
    value.pop("data_path", None)
    return value


def _validate(protocol, project):
    if not isinstance(protocol, dict) or not _REQUIRED.issubset(protocol):
        raise DiscoveryError("Pilot protocol is missing required fields")
    if protocol.get("stage") != "PILOT" or protocol.get("method") not in _METHODS:
        raise DiscoveryError("Only PILOT built-in methods are supported")
    if isinstance(protocol.get("seed"), bool) or not isinstance(protocol.get("seed"), int):
        raise DiscoveryError("Pilot seed must be an integer")
    params = protocol.get("parameters")
    if not isinstance(params, dict) or isinstance(params.get("bootstrap"), bool):
        raise DiscoveryError("Pilot parameters are invalid")
    if not isinstance(params.get("bootstrap"), int):
        raise DiscoveryError("Bootstrap count must be an integer")
    try: bootstrap = int(params["bootstrap"])
    except (KeyError, TypeError, ValueError): raise DiscoveryError("Bootstrap count is required")
    if bootstrap < 1 or bootstrap > 2000: raise DiscoveryError("Bootstrap must be in 1..2000")
    if (not isinstance(params.get("min_effect"), (int, float)) or isinstance(params.get("min_effect"), bool)
            or not math.isfinite(params["min_effect"])):
        raise DiscoveryError("min_effect is required")
    evidence_id = protocol["data_evidence"]
    entry = project.evidence().get(evidence_id)
    if not entry: raise DiscoveryError("Pilot data evidence is missing")
    limits = protocol["limits"]
    if not isinstance(limits, dict) or any(k not in limits for k in ("seconds", "memory_mb", "disk_mb", "cpu_seconds")):
        raise DiscoveryError("Pilot limits are incomplete")
    for key, config_key in (("seconds", "total_seconds"), ("memory_mb", "max_memory_mb"),
                            ("disk_mb", "max_disk_mb"), ("cpu_seconds", "max_cpu_seconds")):
        value = limits[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value <= 0 or value > project.config[config_key]):
            raise DiscoveryError("Pilot limit exceeds project budget: " + key)
    if protocol.get("method") == "group_difference":
        required = ("group_column", "value_column", "treatment", "control")
    else:
        required = ("before_column", "after_column")
    if any(not isinstance(params.get(k), str) or not params[k] for k in required):
        raise DiscoveryError("Pilot column parameters are incomplete")
    return entry


def preregister(project: Project, protocol):
    """Freeze a protocol before any pilot attempt and return its immutable hash."""
    _validate(protocol, project)
    if project.audit():
        raise DiscoveryError("Cannot preregister while evidence is tampered")
    original = _frozen_protocol(protocol)
    registration_sha256 = digest(original)
    if any(event["kind"] == "pilot_registered" and event["payload"].get("protocol_sha256") == registration_sha256
           for event in project.events()):
        raise DiscoveryError("Protocol is already registered")
    project.freeze("pilot_protocol", original)
    project.record("pilot_registered", {"protocol_sha256": registration_sha256,
                                        "protocol_id": protocol["id"],
                                        "data_evidence": protocol["data_evidence"]})
    result = copy.deepcopy(original)
    result["registration_sha256"] = registration_sha256
    return result


def _evidence_file(project, evidence_id):
    item = project.evidence().get(evidence_id)
    if not item: raise DiscoveryError("Pilot evidence is missing")
    path = project.root / item["path"]
    if project.audit(): raise DiscoveryError("Pilot evidence integrity check failed")
    return path


def run_pilot(project: Project, protocol):
    """Execute exactly one previously frozen protocol using the built-in worker."""
    if not isinstance(protocol, dict) or not protocol.get("registration_sha256"):
        raise DiscoveryError("Pilot must be preregistered")
    registration_sha = protocol["registration_sha256"]
    if digest(_frozen_protocol(protocol)) != registration_sha:
        raise DiscoveryError("Registered pilot protocol was modified")
    if not any(event["kind"] == "pilot_registered" and event["payload"].get("protocol_sha256") == registration_sha
               for event in project.events()):
        raise DiscoveryError("Unknown pilot registration")
    if any(event["kind"] == "pilot_result" and event["payload"].get("protocol_sha256") == registration_sha
           for event in project.events()):
        raise DiscoveryError("Pilot registration has already run")
    _validate(protocol, project)
    data_path = _evidence_file(project, protocol["data_evidence"])
    project.consume("max_pilots", 1)
    run_root = project.root / "runs" / registration_sha
    run_root.mkdir(parents=True, exist_ok=True)
    runtime = copy.deepcopy(protocol)
    runtime["data_path"] = str(data_path)
    protocol_path = run_root / "protocol.json"
    write_json(protocol_path, runtime)
    worker = Path(__file__).resolve().with_name("worker.py")
    started = time.monotonic()
    bounded = run_bounded([sys.executable, "-I", str(worker), str(protocol_path)],
                          run_root, protocol["limits"])
    elapsed = max(time.monotonic() - started, bounded.get("elapsed_seconds", 0.0))
    try: project.consume("total_seconds", min(elapsed, project.remaining("total_seconds")))
    except DiscoveryError: pass
    stdout_path, stderr_path = Path(bounded["stdout_path"]), Path(bounded["stderr_path"])
    output_evidence = project.add_evidence(stdout_path, "pilot stdout", "pilot_output")
    stderr_evidence = None
    if stderr_path.stat().st_size or bounded["returncode"] not in (0, None) or bounded["stop_reason"]:
        stderr_evidence = project.add_evidence(stderr_path, "pilot stderr", "pilot_stderr")
    result = {"status": "STOPPED" if bounded["stop_reason"] else ("COMPLETED" if bounded["returncode"] == 0 else "FAILED"),
              "interpretation": "INCONCLUSIVE", "measurement": {}, "output_evidence": output_evidence,
              "stderr_evidence": stderr_evidence, "protocol_sha256": registration_sha,
              "elapsed_seconds": elapsed, "stop_reason": bounded["stop_reason"],
              "platform": bounded.get("platform"), "limitations": bounded.get("limitations", [])}
    if result["status"] == "COMPLETED":
        try:
            payload = json.loads(stdout_path.read_text(encoding="utf-8"))
            result["interpretation"] = payload["interpretation"]
            result["measurement"] = payload["measurement"]
        except (OSError, ValueError, KeyError) as exc:
            result["status"] = "FAILED"
            result["stderr_evidence"] = stderr_evidence or project.add_evidence(stderr_path, "pilot parse failure", "pilot_stderr")
            result["error"] = str(exc)
    project.record("pilot_result", result)
    return result
