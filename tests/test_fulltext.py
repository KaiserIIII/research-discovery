import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError, Project
from rd.fulltext import retrieve_fulltext, verify_region

class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'text/plain'}
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

class FullTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Project.create(Path(self.tmp.name) / 'project', 'full text review')

    def test_open_access_text_is_retrieved_with_line_provenance(self):
        body = b"Methods: fixed cohort.\nResults: effect is bounded.\nLimitations: one dataset.\n"
        with patch('rd.fulltext.urllib.request.urlopen', return_value=Response(body)):
            result = retrieve_fulltext(self.project, 'doi:example', 'https://arxiv.org/abs/example',
                                       lawful_access_basis='open_access')
        self.assertEqual(result['status'], 'FULLTEXT_RETRIEVED')
        self.assertEqual(result['line_count'], 3)
        claim = verify_region(self.project, result['evidence_id'], 'doi:example', 'claim-1',
                              2, 2, 'Results: effect is bounded.', checker='independent-reviewer')
        self.assertEqual(claim['status'], 'VERIFIED')

    def test_metadata_only_and_unapproved_hosts_never_download(self):
        with patch('rd.fulltext.urllib.request.urlopen') as transport:
            with self.assertRaises(DiscoveryError):
                retrieve_fulltext(self.project, 'doi:example', 'https://example.com/paper.txt',
                                   lawful_access_basis='open_access')
        transport.assert_not_called()
        with self.assertRaises(DiscoveryError):
            retrieve_fulltext(self.project, 'doi:example', 'https://arxiv.org/abs/example',
                              lawful_access_basis='abstract_only')

    def test_missing_quote_or_tamper_is_not_verified(self):
        source = Path(self.tmp.name) / 'paper.txt'; source.write_text('one\ntwo\n', encoding='utf-8')
        eid = self.project.add_evidence(source, 'user-provided licensed text', 'fulltext')
        with self.assertRaises(DiscoveryError):
            verify_region(self.project, eid, 'paper', 'claim', 1, 1, 'wrong', checker='reviewer')
        path = self.project.root / self.project.evidence()[eid]['path']; path.write_text('altered\n', encoding='utf-8')
        with self.assertRaises(DiscoveryError):
            verify_region(self.project, eid, 'paper', 'claim', 1, 1, 'altered', checker='reviewer')

if __name__ == '__main__': unittest.main()
