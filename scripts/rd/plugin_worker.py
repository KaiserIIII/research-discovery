"""Subprocess entrypoint for the built-in text delta pilot.

The worker receives a frozen JSON protocol containing absolute paths prepared by
the parent process.  It has no plugin import mechanism and emits one JSON result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def text_delta(left_path: str, right_path: str):
    left = Path(left_path).read_text(encoding="utf-8", errors="replace").splitlines()
    right = Path(right_path).read_text(encoding="utf-8", errors="replace").splitlines()
    left_set, right_set = set(left), set(right)
    return {
        "left_line_count": len(left),
        "right_line_count": len(right),
        "added_lines": len(right_set - left_set),
        "removed_lines": len(left_set - right_set),
        "common_lines": len(left_set & right_set),
        "interpretation": "DESCRIPTIVE_LINE_DELTA",
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print(json.dumps({"status": "ERROR", "error": "protocol path required"}))
        return 2
    try:
        protocol = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        if protocol.get("plugin_id") != "text_delta":
            raise ValueError("unsupported plugin")
        measurement = text_delta(protocol["left_path"], protocol["right_path"])
        print(json.dumps({"status": "COMPLETED", "measurement": measurement,
                          "interpretation": measurement.pop("interpretation")},
                         ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

