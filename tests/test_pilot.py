import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from rd.core import Project, DiscoveryError
    from rd.pilot import preregister, run_pilot
    from rd.limits import run_bounded
    IMPORT_ERROR = None
except ImportError as exc:
    IMPORT_ERROR = str(exc)

def protocol(eid):
    return dict(id='p1', candidate_id='c1', stage='PILOT', hypothesis='Treatment differs by 0.5',
                rivals=['real effect', 'measurement artifact'], data_evidence=eid,
                method='group_difference', parameters=dict(group_column='group', value_column='value',
                    treatment='b', control='a', min_effect=0.5, bootstrap=100),
                primary_observable='mean_difference', variables='group', controls='frozen rows',
                sources='test fixture', stop_rule='one frozen execution',
                predictions=dict(positive='consistent with effect',negative='bounds this effect',
                                 inconclusive='more independent data needed'),
                limits=dict(seconds=5, memory_mb=128, disk_mb=2, cpu_seconds=4), seed=42)

class PilotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, 'Missing implementation: ' + str(IMPORT_ERROR))
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.p = Project.create(self.root/'project', 'test')
        source = self.root/'data.csv'; source.write_text('group,value\na,1\na,1\nb,1\nb,1\n')
        self.eid = self.p.add_evidence(source, 'generated test', 'data')

    def test_negative_is_a_completed_run_with_retained_data(self):
        spec = preregister(self.p, protocol(self.eid))
        result = run_pilot(self.p, spec)
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(result['interpretation'], 'NEGATIVE')
        self.assertEqual(result['measurement']['effect'], 0)
        self.assertTrue(self.p.evidence()[result['output_evidence']])
        self.assertEqual(self.p.audit(), [])

    def test_protocol_cannot_change_after_registration(self):
        spec = preregister(self.p, protocol(self.eid)); spec['hypothesis']='post-hoc'
        with self.assertRaises(DiscoveryError): run_pilot(self.p, spec)

    def test_invalid_data_failure_is_retained(self):
        source=self.root/'bad.csv'; source.write_text('group,value\na,missing\nb,1\n')
        spec=preregister(self.p, protocol(self.p.add_evidence(source,'fixture','data')))
        result=run_pilot(self.p,spec)
        self.assertEqual(result['status'],'FAILED')
        self.assertIsNotNone(result['stderr_evidence'])

    def test_no_unregistered_or_missing_data_execution(self):
        with self.assertRaises(DiscoveryError): run_pilot(self.p,protocol(self.eid))
        spec=protocol('missing')
        with self.assertRaises(DiscoveryError): preregister(self.p,spec)

    def test_timeout_kills_real_process(self):
        result=run_bounded([sys.executable,'-I','-c','import time; time.sleep(5)'],
                           self.root/'bounded',dict(seconds=0.2,memory_mb=128,disk_mb=2,cpu_seconds=1))
        self.assertEqual(result['stop_reason'],'TIMEOUT')
        self.assertLess(result['elapsed_seconds'],3)

    def test_disk_limit_terminates_output(self):
        result=run_bounded([sys.executable,'-I','-c',
                          'import sys,time; sys.stdout.write("x"*2000000); sys.stdout.flush(); time.sleep(2)'],
                          self.root/'bounded',dict(seconds=3,memory_mb=128,disk_mb=0.1,cpu_seconds=2))
        self.assertEqual(result['stop_reason'],'DISK_LIMIT')

    def test_invalid_limits_rejected_before_spawn(self):
        with self.assertRaises(DiscoveryError):
            run_bounded([sys.executable,'-c','pass'],self.root/'bounded',
                        dict(seconds=-1,memory_mb=128,disk_mb=2,cpu_seconds=1))

    def test_positive_and_inconclusive_interpretations_use_preregistered_threshold(self):
        for cid, csv, threshold, expected in [
            ('positive', 'group,value\na,1\na,1\nb,3\nb,3\n', 0.5, 'POSITIVE'),
            ('inconclusive', 'group,value\na,1\na,1\nb,1.5\nb,1.5\n', 0.5, 'INCONCLUSIVE')]:
            with self.subTest(cid=cid):
                source=self.root/(cid+'.csv'); source.write_text(csv)
                spec=protocol(self.p.add_evidence(source,'fixture','data')); spec['id']=cid
                spec['parameters']['min_effect']=threshold
                result=run_pilot(self.p,preregister(self.p,spec))
                self.assertEqual(result['status'],'COMPLETED')
                self.assertEqual(result['interpretation'],expected)

    def test_paired_difference_uses_within_row_changes(self):
        source=self.root/'pairs.csv'; source.write_text('before,after\n1,3\n5,7\n')
        spec=protocol(self.p.add_evidence(source,'paired fixture','data'))
        spec['method']='paired_difference'
        spec['parameters']=dict(before_column='before', after_column='after', min_effect=0.5, bootstrap=100)
        result=run_pilot(self.p,preregister(self.p,spec))
        self.assertEqual(result['measurement']['effect'],2)
        self.assertEqual(result['interpretation'],'POSITIVE')

    def test_failure_consumes_attempt_and_time_budgets(self):
        source=self.root/'bad.csv'; source.write_text('group,value\na,nan\nb,1\n')
        result=run_pilot(self.p,preregister(self.p,protocol(self.p.add_evidence(source,'fixture','data'))))
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual(self.p.remaining('max_pilots'),2)
        self.assertLess(self.p.remaining('total_seconds'),120)
        self.assertEqual(self.p.audit(),[])

    def test_tampered_raw_data_never_executes(self):
        spec=preregister(self.p,protocol(self.eid))
        (self.p.root/self.p.evidence()[self.eid]['path']).write_text('group,value\na,999\nb,0\n')
        with self.assertRaises(DiscoveryError): run_pilot(self.p,spec)
        self.assertEqual(self.p.remaining('max_pilots'),3)

    def test_arbitrary_method_and_excess_bootstrap_are_rejected(self):
        for patch in ('script', 'bootstrap'):
            spec=protocol(self.eid)
            if patch=='script': spec['method']='run_user_script'
            else: spec['parameters']['bootstrap']=2001
            with self.subTest(patch=patch), self.assertRaises(DiscoveryError): preregister(self.p,spec)

    def test_duplicate_registration_and_repeat_execution_are_rejected(self):
        original=protocol(self.eid)
        spec=preregister(self.p,original)
        with self.assertRaises(DiscoveryError): preregister(self.p,original)
        run_pilot(self.p,spec)
        with self.assertRaises(DiscoveryError): run_pilot(self.p,spec)

if __name__=='__main__': unittest.main()
