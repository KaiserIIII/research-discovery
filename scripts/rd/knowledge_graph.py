"""Evidence-backed scientific knowledge graph primitives.

The graph is a traceability structure, not an automated truth oracle. Every
edge needs retained evidence and an explicit confidence state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import DiscoveryError, digest

NODE_TYPES = {
    "Paper", "Claim", "Hypothesis", "Assumption", "Method", "Dataset",
    "ExperimentalCondition", "Result", "Limitation", "Contradiction",
    "OpenQuestion", "Evidence",
}
RELATIONS = {
    "SUPPORTS", "CONTRADICTS", "USES_METHOD", "USES_DATASET", "HAS_ASSUMPTION",
    "BOUNDS", "EXPLAINS", "TESTS", "DERIVED_FROM", "QUALIFIES",
}
CONFIDENCE = {"UNVERIFIED", "METADATA_ONLY", "SUPPORTED", "CONDITIONAL", "REJECTED"}


def create_graph() -> dict[str, Any]:
    return {"schema_version": "2.0", "nodes": [], "edges": [], "decisions": []}


def _node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next((item for item in graph.get("nodes", []) if item.get("id") == node_id), None)


def add_node(graph: dict[str, Any], node_id: str, node_type: str, **data: Any) -> dict[str, Any]:
    if not isinstance(graph, dict) or graph.get("schema_version") != "2.0":
        raise DiscoveryError("Knowledge graph schema must be 2.0")
    if not isinstance(node_id, str) or not node_id.strip() or node_type not in NODE_TYPES:
        raise DiscoveryError("Knowledge graph node needs a valid id and type")
    if _node(graph, node_id):
        raise DiscoveryError("Duplicate knowledge graph node: " + node_id)
    node = {"id": node_id, "type": node_type, "data": deepcopy(data), "uncertainty": "UNVERIFIED"}
    graph["nodes"].append(node)
    return node


def add_edge(
    graph: dict[str, Any], source: str, target: str, relation: str,
    *, evidence_ids: list[str], confidence: str = "UNVERIFIED", conditions: Any = None,
) -> dict[str, Any]:
    if relation not in RELATIONS or confidence not in CONFIDENCE:
        raise DiscoveryError("Unknown graph relation or confidence")
    if not _node(graph, source) or not _node(graph, target):
        raise DiscoveryError("Graph edge references an unknown node")
    if not isinstance(evidence_ids, list) or not evidence_ids or any(not isinstance(item, str) or not item for item in evidence_ids):
        raise DiscoveryError("Every graph edge needs one or more evidence ids")
    edge = {"source": source, "target": target, "relation": relation,
            "evidence_ids": list(dict.fromkeys(evidence_ids)), "confidence": confidence,
            "conditions": deepcopy(conditions) if conditions is not None else {}}
    if any(item == edge for item in graph.get("edges", [])):
        raise DiscoveryError("Duplicate knowledge graph edge")
    graph["edges"].append(edge)
    return edge


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(graph, dict) or graph.get("schema_version") != "2.0":
        return {"status": "FAIL", "findings": ["schema_version must be 2.0"]}
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"status": "FAIL", "findings": ["nodes and edges must be lists"]}
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or node.get("type") not in NODE_TYPES:
            findings.append("invalid node")
            continue
        if node["id"] in ids:
            findings.append("duplicate node: " + node["id"])
        ids.add(node["id"])
    seen_edges = set()
    for edge in edges:
        if not isinstance(edge, dict):
            findings.append("invalid edge")
            continue
        if edge.get("source") not in ids or edge.get("target") not in ids:
            findings.append("edge references unknown node")
        if edge.get("relation") not in RELATIONS or edge.get("confidence") not in CONFIDENCE:
            findings.append("edge relation or confidence is invalid")
        evidence = edge.get("evidence_ids")
        if not isinstance(evidence, list) or not evidence:
            findings.append("edge has no evidence")
        key = (edge.get("source"), edge.get("target"), edge.get("relation"), tuple(evidence or []))
        if key in seen_edges:
            findings.append("duplicate edge")
        seen_edges.add(key)
    return {"status": "PASS" if not findings else "FAIL", "findings": findings,
            "node_count": len(nodes), "edge_count": len(edges)}


def register_graph(project, graph: dict[str, Any]) -> str:
    result = validate_graph(graph)
    if result["status"] != "PASS":
        raise DiscoveryError("Invalid knowledge graph: " + "; ".join(result["findings"]))
    evidence = project.evidence()
    missing = sorted({eid for edge in graph["edges"] for eid in edge["evidence_ids"] if eid not in evidence})
    if missing:
        raise DiscoveryError("Knowledge graph references missing evidence: " + ", ".join(missing))
    frozen = deepcopy(graph)
    graph_id = "G-" + digest(frozen)[:20]
    project.freeze("knowledge_graph", frozen)
    project.record("knowledge_graph", {"graph_id": graph_id, "sha256": digest(frozen),
                                       "node_count": result["node_count"], "edge_count": result["edge_count"]})
    return graph_id
