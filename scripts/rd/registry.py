"""Read-only discovery of local Skills and bounded V4.1 CLI adapters."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .core import DiscoveryError


FRONT_MATTER = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
V41_ROOT = Path(r"C:\Users\17271\.codex\skills\cs-nature-paper")
LOCK_PATH = Path(__file__).resolve().parents[2] / "assets" / "adapters.lock.json"
ADAPTERS = {
    "inventory": {"script": "scripts/skill_router.py", "fixed": ["inventory"]},
    "anchor": {"script": "scripts/evidence_anchor.py", "fixed": ["validate"]},
    "literature": {"script": "scripts/literature_runtime.py", "fixed": ["audit"]},
    "planner": {"script": "scripts/experiment_planner.py", "fixed": ["plan"]},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8-sig")
    match = FRONT_MATTER.match(text)
    if not match:
        raise DiscoveryError(f"Skill has no valid front matter: {path}")
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("\"'")
        if key.strip() in {"name", "description"}:
            values[key.strip()] = value
    if not values.get("name") or not values.get("description"):
        raise DiscoveryError(f"Skill front matter needs name and description: {path}")
    return values, text


def _contract(name: str, description: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {"type": "host_request", "required": ["task"], "description": description},
        {"type": "host_artifact", "required": ["status", "provenance"], "skill": name},
    )


def _load_lock() -> dict[str, Any]:
    try:
        value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"Invalid adapter lock: {LOCK_PATH}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("adapters"), dict):
        raise DiscoveryError("Adapter lock has no adapters object")
    return value


def discover(roots: list[Path]) -> dict[str, Any]:
    """Index real SKILL.md files without importing or executing their contents."""
    capabilities: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen: dict[str, dict[str, Any]] = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            errors.append({"path": str(root), "error": "root does not exist"})
            continue
        files = [root] if root.is_file() and root.name == "SKILL.md" else root.rglob("SKILL.md")
        for path in sorted(files):
            try:
                front, _ = _front_matter(path)
                name = front["name"].strip()
                description = front["description"].strip()
                input_contract, output_contract = _contract(name, description)
                record = {
                    "id": name,
                    "name": name,
                    "path": str(path.resolve()),
                    "description": description,
                    "interface": {"type": "host_workflow", "available": False},
                    "input_contract": input_contract,
                    "output_contract": output_contract,
                    "availability": "HOST_WORKFLOW",
                    "limitations": ["SKILL.md is guidance; no unknown code is imported or executed", "business behavior is unprobed"],
                    "tasks": [],
                    "fallback": "HOST_WORKFLOW",
                    "source_sha256": _sha256(path),
                }
                if name in seen:
                    conflicts.append({"id": name, "paths": [seen[name]["path"], record["path"]]})
                else:
                    seen[name] = record
                    capabilities.append(record)
            except (OSError, UnicodeError, DiscoveryError) as exc:
                errors.append({"path": str(path), "error": str(exc)})
    return {"capabilities": capabilities, "conflicts": conflicts, "errors": errors}


def _resolve_script(skill_path: Path, relative: str) -> tuple[Path, Path]:
    candidate = Path(skill_path)
    root = candidate if candidate.is_dir() else candidate.parent
    if candidate.is_file() and candidate.name == "SKILL.md":
        root = candidate.parent
    if root.name == "scripts":
        root = root.parent
    script = (root / relative).resolve()
    if not script.is_file() or not script.is_relative_to(root.resolve()):
        raise DiscoveryError(f"Adapter script is unavailable: {script}")
    return root.resolve(), script


def _locked_root(skill_path: Path) -> Path:
    candidate = Path(skill_path).resolve()
    current = candidate if candidate.is_dir() else candidate.parent
    while True:
        if (current / "assets" / "registry" / "capabilities.json").is_file() and (current / "scripts").is_dir():
            return current
        if current.parent == current:
            raise DiscoveryError(f"Cannot locate V4.1 skill root from: {candidate}")
        current = current.parent


def _locked_adapter(adapter: str, root: Path, script: Path) -> dict[str, Any]:
    lock = _load_lock()
    row = lock["adapters"].get(adapter)
    if not isinstance(row, dict):
        raise DiscoveryError(f"Unknown V4.1 adapter: {adapter}")
    expected_path = str(row.get("script", "")).replace("\\", "/")
    actual_path = str(script.relative_to(root)).replace("\\", "/")
    if actual_path != expected_path:
        raise DiscoveryError(f"Adapter script path is not locked: {actual_path}")
    actual_sha = _sha256(script)
    if actual_sha != row.get("sha256"):
        raise DiscoveryError(f"Adapter source hash mismatch: {actual_path}")
    return row


def _safe_args(adapter: str, args: list[str], output_dir: Path) -> list[str]:
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise DiscoveryError("Adapter args must be a list of strings")
    if adapter == "inventory":
        if args:
            raise DiscoveryError("inventory does not accept arguments")
        return ["inventory"]
    if adapter == "anchor":
        if not (1 <= len(args) <= 4) or args[0].startswith("-"):
            raise DiscoveryError("anchor requires FILE with optional --deep --root ROOT")
        position = 1
        while position < len(args):
            if args[position] == "--deep":
                position += 1
            elif args[position] == "--root" and position + 1 < len(args) and not args[position + 1].startswith("-"):
                position += 2
            else:
                raise DiscoveryError("anchor has unsupported arguments")
        if args.count("--deep") > 1 or args.count("--root") > 1:
            raise DiscoveryError("anchor has unsupported arguments")
        return ["validate", *args]
    if adapter == "literature":
        if len(args) != 1 or args[0].startswith("-"):
            raise DiscoveryError("literature requires one registry FILE")
        return ["audit", args[0]]
    if adapter == "planner":
        if len(args) not in {1, 3} or args[0].startswith("-") or (len(args) == 3 and args[1] != "--output"):
            raise DiscoveryError("planner requires OPTIONS FILE with optional --output FILE")
        if len(args) == 3 and not (Path(args[2]) if Path(args[2]).is_absolute() else output_dir / args[2]).resolve().is_relative_to(output_dir.resolve()):
            raise DiscoveryError("planner output must remain under output_dir")
        return ["plan", *args]
    raise DiscoveryError(f"Unknown V4.1 adapter: {adapter}")


def invoke_v41(adapter: str, skill_path: Path, args: list[str], output_dir: Path) -> dict[str, Any]:
    """Run one locked, fixed-argument V4.1 CLI with a short timeout."""
    if adapter not in ADAPTERS:
        raise DiscoveryError(f"Unknown V4.1 adapter: {adapter}")
    root = _locked_root(Path(skill_path))
    if not root.exists():
        raise DiscoveryError(f"V4.1 skill path does not exist: {root}")
    root, script = _resolve_script(root, ADAPTERS[adapter]["script"])
    row = _locked_adapter(adapter, root, script)
    output_dir = Path(output_dir).resolve()
    invocation_args = _safe_args(adapter, args, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = ["python", str(script), *invocation_args]
    try:
        completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True, timeout=15, check=False)
    except OSError as exc:
        return {"status": "ERROR", "exit_code": None, "stdout": "", "stderr": str(exc), "command": command, "source_sha256": row["sha256"]}
    except subprocess.TimeoutExpired as exc:
        return {"status": "ERROR", "exit_code": None, "stdout": _text(exc.stdout), "stderr": _text(exc.stderr) or "timeout", "command": command, "source_sha256": row["sha256"]}
    return {"status": "OK" if completed.returncode == 0 else "ERROR", "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "command": command, "source_sha256": row["sha256"]}


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
