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

if __name__=='__main__': unittest.main()
