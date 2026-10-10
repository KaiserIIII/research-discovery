"""Registry for bounded, auditable non-CSV discovery pilot plugins.

Only plugins listed here can be executed.  A registry record describes a
contract; it is not permission to execute arbitrary user code.
"""
from __future__ import annotations

from copy import deepcopy

from .core import DiscoveryError


_PLUGINS = {
    "text_delta": {
        "id": "text_delta",
        "version": "1.0",
        "availability": "VERIFIED_EXECUTABLE",
        "input_contract": {"left": "text evidence", "right": "text evidence"},
        "output_contract": ["added_lines", "removed_lines", "common_lines"],
        "entrypoint": "rd.plugin_worker:text_delta",
        "limitations": [
            "Compares normalized UTF-8 lines and does not infer semantic equivalence.",
            "Runs under the stdlib resource governor; this is not a security sandbox.",
        ],
    },
}


def discover_plugins():
    """Return a defensive copy of the executable plugin capability registry."""
    return {key: deepcopy(value) for key, value in _PLUGINS.items()}


def get_plugin(plugin_id: str):
    """Resolve one explicitly registered plugin or fail closed."""
    if not isinstance(plugin_id, str) or plugin_id not in _PLUGINS:
        raise DiscoveryError("Unknown pilot plugin: " + str(plugin_id))
    return deepcopy(_PLUGINS[plugin_id])

