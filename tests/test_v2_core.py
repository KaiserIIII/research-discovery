import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rd.core import DiscoveryError, Project
from rd.evaluation import compare_runs, record_run
from rd.knowledge_graph import add_edge, add_node, create_graph, register_graph, validate_graph
from rd.pilot_discovery import preregister_static_analysis, run_static_analysis


class V2CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = Project.create(self.root / "project", "software research")

    def test_knowledge_graph_requires_evidence_backed_typed_edges(self):
        source = self.root / "source.txt"
        source.write_text("A mechanism is observed.\n", encoding="utf-8")
        evidence_id = self.project.add_evidence(source, "synthetic primary source", "text")
        graph = create_graph()
        add_node(graph, "paper:1", "Paper", title="A paper")
        add_node(graph, "claim:1", "Claim", text="A mechanism is observed")
        add_edge(graph, "paper:1", "claim:1", "SUPPORTS", evidence_ids=[evidence_id], confidence="SUPPORTED")
        self.assertEqual(validate_graph(graph)["status"], "PASS")
        graph_id = register_graph(self.project, graph)
        self.assertTrue(graph_id.startswith("G-"))

    def test_knowledge_graph_rejects_unproven_edge(self):
        graph = create_graph()
        add_node(graph, "a", "Claim")
        add_node(graph, "b", "Claim")
        with self.assertRaises(DiscoveryError):
            add_edge(graph, "a", "b", "SUPPORTS", evidence_ids=[])

    def test_static_analysis_pilot_is_preregistered_and_does_not_execute_source(self):
        source = self.root / "sample.py"
        source.write_text("import ast\n\ndef f(x):\n    if x:\n        return 1\n    return 0\n", encoding="utf-8")
        evidence_id = self.project.add_evidence(source, "user-provided source", "source_code")
        protocol = {
            "id": "static-1",
            "candidate_id": "c-static",
            "stage": "PILOT",
            "source_evidence": evidence_id,
            "metrics": ["functions", "branches", "imports", "lines"],
            "controls": "parse only; never import or execute",
            "limits": {"seconds": 5, "memory_mb": 128, "disk_mb": 2, "cpu_seconds": 4},
            "seed": 7,
            "stop_rule": "one deterministic AST pass",
            "predictions": {"positive": "branches are present", "negative": "no branch is present"},
        }
        registered = preregister_static_analysis(self.project, protocol)
        result = run_static_analysis(self.project, registered)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["measurement"]["functions"], 1)
        self.assertEqual(result["measurement"]["branches"], 1)
        self.assertEqual(result["interpretation"], "POSITIVE")

    def test_evaluation_records_and_compares_baselines(self):
        record_run(self.project, "sol_direct", "case-1", {"fact_accuracy": 0.5}, cost=10, actor="Sol")
        record_run(self.project, "v1.0.1", "case-1", {"fact_accuracy": 0.6}, cost=9, actor="Sol")
        record_run(self.project, "v2.0", "case-1", {"fact_accuracy": 0.8}, cost=8, actor="Sol")
        report = compare_runs(self.project)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["metrics"]["fact_accuracy"]["delta_v2_vs_v1"], 0.2)
        self.assertEqual(report["cost"]["v2.0"], 8.0)


if __name__ == "__main__":
    unittest.main()
