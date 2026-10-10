import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError, Project
from rd.plugins import discover_plugins, get_plugin
from rd.plugin_pilot import preregister_plugin, run_plugin_pilot

class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.project=Project.create(self.root/'project','text provenance')
        a=self.root/'a.txt'; b=self.root/'b.txt'
        a.write_text('same\nremoved\n',encoding='utf-8'); b.write_text('same\nadded\n',encoding='utf-8')
        self.a=self.project.add_evidence(a,'synthetic text fixture','text')
        self.b=self.project.add_evidence(b,'synthetic text fixture','text')

    def test_builtin_plugin_has_contract_and_runs_real_non_csv_pilot(self):
        plugins=discover_plugins(); self.assertIn('text_delta',plugins)
        plugin=get_plugin('text_delta'); self.assertEqual(plugin['availability'],'VERIFIED_EXECUTABLE')
        protocol={'id':'text-1','plugin_id':'text_delta','stage':'PILOT','inputs':{'left':self.a,'right':self.b},
                  'limits':{'seconds':5,'memory_mb':128,'disk_mb':2,'cpu_seconds':4},
                  'seed':1,'stop_rule':'one bounded comparison','expected_output':'line_delta'}
        frozen=preregister_plugin(self.project,protocol); result=run_plugin_pilot(self.project,frozen)
        self.assertEqual(result['status'],'COMPLETED'); self.assertEqual(result['measurement']['added_lines'],1)

    def test_unknown_or_tampered_plugin_is_rejected(self):
        with self.assertRaises(DiscoveryError):
            preregister_plugin(self.project,{'id':'x','plugin_id':'unknown','inputs':{'left':self.a,'right':self.b}})
        protocol={'id':'text-2','plugin_id':'text_delta','stage':'PILOT','inputs':{'left':self.a,'right':self.b},
                  'limits':{'seconds':5,'memory_mb':128,'disk_mb':2,'cpu_seconds':4},'seed':1,
                  'stop_rule':'one','expected_output':'line_delta'}
        frozen=preregister_plugin(self.project,protocol); frozen['plugin_id']='forged'
        with self.assertRaises(DiscoveryError): run_plugin_pilot(self.project,frozen)

if __name__ == '__main__': unittest.main()
