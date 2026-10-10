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
        add_edge(graph, "paper:1", "claim:1", "SUPPORTS", evidence_ids=[evidence_id], confidence="SUPPORTED",
                 anchors={evidence_id: {"start_line": 1, "end_line": 1,
                                        "quote": "A mechanism is observed.", "relation": "SUPPORTS"}})
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
        self.assertEqual(result["interpretation"], "INCONCLUSIVE")
        self.assertEqual(result["execution_mode"], "AST_PARSE_ONLY_BOUNDED")
        self.assertTrue(result["output_evidence"])

    def test_evaluation_records_and_compares_baselines(self):
        # Different cases/budgets cannot create a direct delta.
        record_run(self.project, "v1.0.1", "case-a", {"fact_accuracy": 0.6}, cost=9, actor="Sol", source="real")
        record_run(self.project, "v2.0", "case-b", {"fact_accuracy": 0.8}, cost=8, actor="Sol", source="real")
        # A matched real pair can be compared even when observed costs differ;
        # the allocated budget and all frozen conditions must match.
        conditions = {"dataset": "frozen-1", "prompt": "p"}
        record_run(self.project, "v1.0.1", "case-1", {"fact_accuracy": 0.6}, cost=9, budget=10, actor="Sol", conditions=conditions, source="real")
        record_run(self.project, "v2.0", "case-1", {"fact_accuracy": 0.8}, cost=8, budget=10, actor="Sol", conditions=conditions, source="real")
        # Synthetic fixtures with matching keys remain blocked from uplift claims.
        record_run(self.project, "v1.0.1", "synthetic", {"fact_accuracy": 0.1}, cost=1, actor="Sol")
        record_run(self.project, "v2.0", "synthetic", {"fact_accuracy": 0.9}, cost=1, actor="Sol")
        report = compare_runs(self.project)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["metrics"]["fact_accuracy"]["delta_v2_vs_v1"], 0.2)
        self.assertEqual(report["means_by_source"]["real"]["v2.0"]["fact_accuracy"], 0.8)
        self.assertEqual(report["pairing"]["real_pairs"], 1)
        self.assertTrue(report["pairing"]["synthetic_deltas_blocked"])

    def test_verified_graph_edge_requires_original_text_anchor(self):
        graph = create_graph()
        add_node(graph, "a", "Claim")
        add_node(graph, "b", "Claim")
        with self.assertRaises(DiscoveryError):
            add_edge(graph, "a", "b", "SUPPORTS", evidence_ids=["E1"], confidence="SUPPORTED")

    def test_graph_register_rejects_changed_anchor_and_metadata_only_support(self):
        source = self.root / "source.txt"
        source.write_text("Observed mechanism.\n", encoding="utf-8")
        evidence_id = self.project.add_evidence(source, "primary source", "text")
        graph = create_graph(); add_node(graph, "a", "Claim"); add_node(graph, "b", "Claim")
        add_edge(graph, "a", "b", "SUPPORTS", evidence_ids=[evidence_id], confidence="SUPPORTED",
                 anchors={evidence_id: {"start_line": 1, "end_line": 1, "quote": "Forged.", "relation": "SUPPORTS"}})
        with self.assertRaises(DiscoveryError):
            register_graph(self.project, graph)

        metadata = self.root / "metadata.json"; metadata.write_text("{}\n", encoding="utf-8")
        metadata_id = self.project.add_evidence(metadata, "metadata API", "literature_query")
        graph2 = create_graph(); add_node(graph2, "a", "Claim"); add_node(graph2, "b", "Claim")
        add_edge(graph2, "a", "b", "SUPPORTS", evidence_ids=[metadata_id], confidence="SUPPORTED",
                 anchors={metadata_id: {"start_line": 1, "end_line": 1, "quote": "{}", "relation": "SUPPORTS"}})
        with self.assertRaises(DiscoveryError):
            register_graph(self.project, graph2)


if __name__ == "__main__":
    unittest.main()
