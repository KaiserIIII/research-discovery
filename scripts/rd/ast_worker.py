"""Bounded AST-only worker used by the static-analysis pilot.

The worker reads source text and never imports, compiles or executes it.  It
is a separate process so the declared wall, CPU, memory and disk limits are
actually applied by ``rd.limits.run_bounded`` on Windows and POSIX hosts.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def measure(text: str) -> dict[str, int]:
    lines = len(text.splitlines())
    todo_markers = sum(text.lower().count(marker) for marker in ("todo", "fixme"))
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"lines": lines, "functions": 0, "classes": 0, "imports": 0,
                "branches": 0, "try_blocks": 0, "todo_markers": todo_markers,
                "syntax_error": 1, "syntax_error_line": exc.lineno or 0}
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


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print(json.dumps({"status": "ERROR", "error": "protocol path required"}))
        return 2
    try:
        protocol = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        source = Path(protocol["source_path"])
        result = measure(source.read_text(encoding="utf-8"))
        print(json.dumps({"status": "COMPLETED", "measurement": result}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
