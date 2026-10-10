import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError, Project
from rd.discovery import request_hypotheses, receive_host

class DiscoveryUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project=Project.create(Path(self.tmp.name)/'project','software measurement')

    def test_hypothesis_request_requires_actual_host_response_contract(self):
        request=request_hypotheses(self.project,'software supply chain',[],actor='Sol')
        self.assertEqual(request['status'],'HOST_REQUIRED')
        with self.assertRaises(DiscoveryError):
            receive_host(self.project,{'request_id':request['request_id'],'input_sha256':request['input_sha256'],
                                      'actor':'Sol','model':'unknown','findings':[],'artifact_ids':[]})

    def test_three_host_candidates_are_materially_distinct_and_provenanced(self):
        request=request_hypotheses(self.project,'software supply chain',[],actor='Sol')
        base=dict(significance='A bounded test can alter the next study.',ideal_result='A new boundary is measured.',
                  claim='The mechanism changes under condition X.',prediction='Effect exceeds 0.5.',falsifier='No effect.',
                  rivals=['artifact','mechanism'],pilot='Compare frozen controls.',resources={'seconds':5,'memory_mb':128,'disk_mb':2},
                  failure_information='A negative result bounds the claim.',followup='Independent replication.',evidence_ids=[],nearest=[],search_ids=[])
        candidates=[dict(base,id='a',route='boundary',question='Which boundary matters?',increment_kind='boundary_evidence'),
                    dict(base,id='b',route='mechanism',question='Which mechanism explains it?',increment_kind='mechanism'),
                    dict(base,id='c',route='transfer',question='Does a transfer expose it?',increment_kind='new_capability')]
        result=receive_host(self.project,dict(request_id=request['request_id'],input_sha256=request['input_sha256'],
                      actor='Sol',model='gpt-6-astra',findings=['host reasoning recorded'],artifact_ids=[],candidates=candidates))
        self.assertEqual(result['status'],'RECEIVED'); self.assertEqual(result['candidate_count'],3)

if __name__ == '__main__': unittest.main()
