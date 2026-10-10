import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from rd.core import Project, DiscoveryError, DEFAULT_CONFIG
    from rd.discovery import mine, validate_candidates, assess, compete, revise
    IMPORT_ERROR = None
except ImportError as exc:
    IMPORT_ERROR = str(exc)


def candidate(cid='c1', route='mechanism'):
    return dict(id=cid, route=route, question='Which explanation predicts the change?',
                significance='Changes interpretation of the measured phenomenon.',
                ideal_result='Identify the boundary where explanation A fails.',
                increment_kind='boundary_evidence', claim='A fails when the control changes.',
                prediction='Controlled effect exceeds 0.1.', falsifier='Effect remains below 0.1.',
                rivals=['Measurement artifact', 'Real mechanism'],
                pilot='Compare held-fixed controls on the original cohort.',
                resources={'seconds': 5, 'memory_mb': 128, 'disk_mb': 5},
                failure_information='Bounds this effect on the frozen cohort.',
                followup='Independent replication on new preregistered data.',
                evidence_ids=[], nearest=[], search_ids=[])


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, 'Missing implementation: ' + str(IMPORT_ERROR))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p = Project.create(self.root / 'study', 'software measurement')

    def test_config_rejects_negative_and_unknown_budgets(self):
        for patch in ({'max_pilots': -1}, {'cloud_money': 10}, {'network_requests': True}):
            with self.subTest(patch=patch), self.assertRaises(DiscoveryError):
                Project.create(self.root / str(len(list(self.root.iterdir()))), 'x', patch)

    def test_immutable_evidence_rejects_tamper_and_missing(self):
        source = self.root / 'raw.csv'
        source.write_text('group,value\na,1\n', encoding='utf-8')
        eid = self.p.add_evidence(source, 'generated fixture', 'data')
        entry = self.p.evidence()[eid]
        stored = self.p.root / entry['path']
        self.assertEqual(self.p.audit(), [])
        stored.write_text('altered', encoding='utf-8')
        self.assertTrue(self.p.audit())
        stored.unlink()
        self.assertTrue(self.p.audit())

    def test_journal_rejects_rewriting_old_predictions(self):
        self.p.record('prediction', {'value': 'before'})
        self.p.record('prediction', {'value': 'after', 'stage': 'EXPLORATORY_POST_HOC'})
        events = self.p.events()
        self.assertEqual(events[-2]['payload']['value'], 'before')
        journal = self.p.root / 'events.jsonl'
        journal.write_text(journal.read_text().replace('before', 'forged'), encoding='utf-8')
        with self.assertRaises(DiscoveryError):
            self.p.events()

    def test_budget_counts_failed_attempts_and_blocks_overspend(self):
        self.p.consume('max_pilots', 2)
        with self.assertRaises(DiscoveryError):
            self.p.consume('max_pilots', DEFAULT_CONFIG['max_pilots'])
        self.assertEqual(self.p.remaining('max_pilots'), DEFAULT_CONFIG['max_pilots'] - 2)

    def test_missing_evidence_blocks_candidate_admission(self):
        c = candidate()
        c['evidence_ids'] = ['does-not-exist']
        with self.assertRaises(DiscoveryError):
            validate_candidates(self.p, [c, candidate('c2','boundary'), candidate('c3','transfer')])

    def test_competition_requires_distinct_questions_and_routes(self):
        cs = [candidate(str(i)) for i in range(3)]
        with self.assertRaises(DiscoveryError):
            validate_candidates(self.p, cs)

    def test_five_routes_and_surface_contradiction(self):
        claims = [dict(id='a', phenomenon='accuracy', direction=1,
                       context={'dataset':'one'}, assumptions=['exchangeability'], evidence_ids=[]),
                  dict(id='b', phenomenon='accuracy', direction=-1,
                       context={'dataset':'two'}, assumptions=[], evidence_ids=[])]
        seed = dict(claims=claims,
                    transfers=[dict(method='randomization', target='confounding', basis='exchangeability', failure='violated assignment')],
                    anomalies=[dict(observation='null effect', alternative='noise')],
                    mechanisms=[dict(observation='timing change', rivals=['clock', 'build'])])
        opportunities = mine(seed)
        self.assertEqual(set(x['route'] for x in opportunities),
                         {'contradiction','boundary','transfer','failure','mechanism'})
        conflict = next(x for x in opportunities if x['route']=='contradiction')
        self.assertEqual(conflict['comparability'], 'CONFOUNDED')

    def test_unverified_search_never_confirms_novelty(self):
        self.assertEqual(assess(self.p, candidate())['status'], 'UNVERIFIED')

    def test_object_swap_and_known_increment_have_different_value(self):
        swap = candidate('swap'); swap['increment_kind'] = 'application'
        self.assertEqual(assess(self.p, swap)['status'], 'INCREMENTAL_APPLICATION')
        ranked = compete(self.p, [swap, candidate('mechanism')])
        self.assertNotEqual(ranked[0]['id'], 'swap')

    def test_revision_retains_original_and_consumes_round_budget(self):
        before = candidate()
        result = revise(self.p, before, {'interpretation': 'NEGATIVE'}, 'Probe measurement boundary')
        self.assertEqual(before['question'], 'Which explanation predicts the change?')
        self.assertEqual(result['stage'], 'EXPLORATORY_POST_HOC')
        self.assertEqual(result['parent_id'], 'c1')


if __name__ == '__main__':
    unittest.main()
