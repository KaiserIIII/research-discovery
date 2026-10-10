import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import Project
from rd.handoff import export_dossier, validate_dossier, compatibility

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

if __name__=='__main__': unittest.main()
