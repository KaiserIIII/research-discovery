import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import Project
from rd.handoff import export_dossier, validate_dossier, compatibility
from rd.knowledge_graph import add_edge, add_node, create_graph, register_graph
from rd.evaluation import record_run

class HandoffTests(unittest.TestCase):
    def test_export_is_self_consistent_and_v41_probe_is_read_only(self):
        root=Path(tempfile.mkdtemp()); project=Project.create(root/'project','test'); dossier=root/'dossier'
        exported=export_dossier(project,dossier)
        self.assertEqual(exported['status'],'PASS')
        self.assertEqual(validate_dossier(dossier)['status'],'PASS')
        result=compatibility(dossier,Path(r'C:\Users\17271\.codex\skills\cs-nature-paper'))
        self.assertIn(result['status'],{'PASS','CONDITIONAL'})
        self.assertIn(result['v41_inventory_status'],{'OK','NOT_RUN'})
        self.assertIn(result['format_compatibility'],{'FORMAT_COMPATIBLE','FORMAT_INVALID'})
        self.assertIn(result['scientific_review'],{'SCIENTIFIC_REVIEW_REQUIRED'})
        self.assertIn(result['admission_decision'],{'SCIENTIFIC_REVIEW_REQUIRED','NEEDS_EVIDENCE'})

    def test_dossier_requires_embedded_evidence_after_move(self):
        root=Path(tempfile.mkdtemp()); project=Project.create(root/'project','test')
        source=root/'source.txt'; source.write_text('source evidence\n',encoding='utf-8')
        project.add_evidence(source,'synthetic source','fulltext')
        dossier=root/'dossier'; export_dossier(project,dossier)
        moved=root/'moved'; dossier.rename(moved)
        self.assertEqual(validate_dossier(moved)['status'],'PASS')
        evidence=list((moved/'evidence').glob('*'))
        self.assertTrue(evidence)
        evidence[0].unlink()
        self.assertEqual(validate_dossier(moved)['status'],'FAIL')

    def test_v2_artifacts_are_exported_when_project_contains_them(self):
        root=Path(tempfile.mkdtemp()); project=Project.create(root/'project','v2 export')
        source=root/'source.txt'; source.write_text('claim\n',encoding='utf-8')
        eid=project.add_evidence(source,'synthetic source','text')
        graph=create_graph(); add_node(graph,'paper:1','Paper'); add_node(graph,'claim:1','Claim')
        add_edge(graph,'paper:1','claim:1','SUPPORTS',evidence_ids=[eid],confidence='SUPPORTED')
        register_graph(project,graph)
        record_run(project,'sol_direct','case-1',{'accuracy':0.5},cost=2,actor='Sol')
        dossier=root/'dossier'; export_dossier(project,dossier)
        self.assertTrue((dossier/'knowledge_graph.json').is_file())
        self.assertTrue((dossier/'evaluation_report.json').is_file())
        self.assertEqual(validate_dossier(dossier)['status'],'PASS')

if __name__=='__main__': unittest.main()
