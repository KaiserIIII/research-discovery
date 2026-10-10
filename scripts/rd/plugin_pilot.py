"""Preregistration and bounded execution for non-CSV pilot plugins."""
from __future__ import annotations

import copy
import json
import math
import sys
import time
from pathlib import Path

from .core import DiscoveryError, Project, contained, digest, write_json
from .limits import run_bounded
from .plugins import get_plugin


_REQUIRED = {"id", "plugin_id", "stage", "inputs", "limits", "seed", "stop_rule", "expected_output"}


def _frozen(protocol):
    value = copy.deepcopy(protocol)
    value.pop("registration_sha256", None)
    value.pop("left_path", None)
    value.pop("right_path", None)
    return value


def _validate(protocol, project):
    if not isinstance(protocol, dict) or not _REQUIRED.issubset(protocol):
        raise DiscoveryError("Plugin protocol is missing required fields")
    if protocol.get("stage") != "PILOT":
        raise DiscoveryError("Plugin protocol stage must be PILOT")
    plugin = get_plugin(protocol.get("plugin_id"))
    if plugin.get("availability") != "VERIFIED_EXECUTABLE":
        raise DiscoveryError("Plugin is not executable")
    if isinstance(protocol.get("seed"), bool) or not isinstance(protocol.get("seed"), int):
        raise DiscoveryError("Plugin seed must be an integer")
    if not isinstance(protocol.get("stop_rule"), str) or not protocol["stop_rule"].strip():
        raise DiscoveryError("Plugin stop_rule is required")
    if not isinstance(protocol.get("expected_output"), str) or not protocol["expected_output"].strip():
        raise DiscoveryError("Plugin expected_output is required")
    inputs = protocol["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"left", "right"}:
        raise DiscoveryError("text_delta needs left and right evidence IDs")
    for key in ("left", "right"):
        entry = project.evidence().get(inputs[key])
        if not entry:
            raise DiscoveryError("Plugin input evidence is missing: " + str(inputs[key]))
        if entry.get("kind") not in {"text", "fulltext", "public_primary_source"}:
            raise DiscoveryError("Plugin input must be text evidence: " + str(inputs[key]))
        path = contained(project.root, entry["path"])
        if not path.is_file():
            raise DiscoveryError("Plugin input evidence is missing on disk: " + str(inputs[key]))
    limits = protocol["limits"]
    if not isinstance(limits, dict) or any(k not in limits for k in ("seconds", "memory_mb", "disk_mb", "cpu_seconds")):
        raise DiscoveryError("Plugin limits are incomplete")
    for key, config_key in (("seconds", "total_seconds"), ("memory_mb", "max_memory_mb"),
                            ("disk_mb", "max_disk_mb"), ("cpu_seconds", "max_cpu_seconds")):
        value = limits[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or value > project.config[config_key]:
            raise DiscoveryError("Plugin limit exceeds project budget: " + key)
    return plugin


def preregister_plugin(project: Project, protocol):
    _validate(protocol, project)
    if project.audit():
        raise DiscoveryError("Cannot preregister while evidence is tampered")
    frozen = _frozen(protocol)
    registration_sha256 = digest(frozen)
    if any(event["kind"] == "plugin_registered" and event["payload"].get("protocol_sha256") == registration_sha256
           for event in project.events()):
        raise DiscoveryError("Plugin protocol is already registered")
    project.freeze("plugin_protocol", frozen)
    project.record("plugin_registered", {"protocol_sha256": registration_sha256,
                                          "protocol_id": protocol["id"],
                                          "plugin_id": protocol["plugin_id"],
                                          "inputs": protocol["inputs"]})
    result = copy.deepcopy(frozen)
    result["registration_sha256"] = registration_sha256
    return result


def run_plugin_pilot(project: Project, protocol):
    if not isinstance(protocol, dict) or not protocol.get("registration_sha256"):
        raise DiscoveryError("Plugin pilot must be preregistered")
    registration_sha = protocol["registration_sha256"]
    if digest(_frozen(protocol)) != registration_sha:
        raise DiscoveryError("Registered plugin protocol was modified")
    if not any(event["kind"] == "plugin_registered" and event["payload"].get("protocol_sha256") == registration_sha
               for event in project.events()):
        raise DiscoveryError("Unknown plugin registration")
    if any(event["kind"] == "plugin_result" and event["payload"].get("protocol_sha256") == registration_sha
           for event in project.events()):
        raise DiscoveryError("Plugin registration has already run")
    _validate(protocol, project)
    left = project.evidence()[protocol["inputs"]["left"]]
    right = project.evidence()[protocol["inputs"]["right"]]
    project.consume("max_pilots", 1)
    run_root = project.root / "runs" / ("plugin-" + registration_sha)
    run_root.mkdir(parents=True, exist_ok=True)
    runtime = copy.deepcopy(protocol)
    runtime["left_path"] = str(contained(project.root, left["path"]))
    runtime["right_path"] = str(contained(project.root, right["path"]))
    protocol_path = run_root / "protocol.json"
    write_json(protocol_path, runtime)
    worker = Path(__file__).resolve().with_name("plugin_worker.py")
    started = time.monotonic()
    bounded = run_bounded([sys.executable, "-I", str(worker), str(protocol_path)], run_root, protocol["limits"])
    elapsed = max(time.monotonic() - started, bounded.get("elapsed_seconds", 0.0))
    try:
        project.consume("total_seconds", min(elapsed, project.remaining("total_seconds")))
    except DiscoveryError:
        pass
    stdout_path, stderr_path = Path(bounded["stdout_path"]), Path(bounded["stderr_path"])
    output_evidence = project.add_evidence(stdout_path, "plugin pilot stdout", "pilot_output")
    stderr_evidence = None
    if stderr_path.stat().st_size or bounded["returncode"] not in (0, None) or bounded["stop_reason"]:
        stderr_evidence = project.add_evidence(stderr_path, "plugin pilot stderr", "pilot_stderr")
    result = {"status": "STOPPED" if bounded["stop_reason"] else ("COMPLETED" if bounded["returncode"] == 0 else "FAILED"),
              "interpretation": "INCONCLUSIVE", "measurement": {}, "output_evidence": output_evidence,
              "stderr_evidence": stderr_evidence, "protocol_sha256": registration_sha,
              "plugin_id": protocol["plugin_id"], "elapsed_seconds": elapsed,
              "stop_reason": bounded["stop_reason"], "platform": bounded.get("platform"),
              "limitations": bounded.get("limitations", [])}
    if result["status"] == "COMPLETED":
        try:
            payload = json.loads(stdout_path.read_text(encoding="utf-8"))
            if payload.get("status") != "COMPLETED":
                raise ValueError(payload.get("error", "plugin worker failed"))
            result["interpretation"] = payload["interpretation"]
            result["measurement"] = payload["measurement"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["status"] = "FAILED"
            result["stderr_evidence"] = stderr_evidence or project.add_evidence(stderr_path, "plugin parse failure", "pilot_stderr")
            result["error"] = str(exc)
    project.record("plugin_result", result)
    return result

