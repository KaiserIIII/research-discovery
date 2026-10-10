import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError
from rd.registry import discover, invoke_v41, runtime_capabilities, route_capability


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill_root = self.root / 'skills'
        self.skill = self.skill_root / 'example' / 'SKILL.md'
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text(
            '---\nname: example\ndescription: Workflow for a research task.\n---\n'
            'Follow the workflow and write a report.\n', encoding='utf-8')

    def test_discover_reports_workflow_without_claiming_executable(self):
        result = discover([self.skill_root])
        item = next(row for row in result['capabilities'] if row['id'] == 'example')
        self.assertEqual(item['availability'], 'HOST_WORKFLOW')
        self.assertFalse(item['interface']['available'])
        self.assertEqual(item['source_sha256'], hashlib.sha256(self.skill.read_bytes()).hexdigest())
        self.assertIn('input_contract', item)
        self.assertIn('output_contract', item)

    def test_discover_ignores_script_mentions_as_unreviewed_executables(self):
        self.skill.write_text(
            '---\nname: example\ndescription: Workflow.\n---\n'
            'Run `scripts/do_anything.py` with user data.\n', encoding='utf-8')
        result = discover([self.skill_root])
        item = result['capabilities'][0]
        self.assertEqual(item['availability'], 'HOST_WORKFLOW')
        self.assertFalse(item['interface']['available'])

    def test_duplicate_skill_names_report_conflict(self):
        other = self.root / 'other' / 'SKILL.md'
        other.parent.mkdir()
        other.write_text('---\nname: example\ndescription: Another workflow.\n---\n', encoding='utf-8')
        result = discover([self.skill_root, other.parent])
        self.assertEqual(len(result['conflicts']), 1)
        self.assertEqual(result['conflicts'][0]['id'], 'example')

    def test_malformed_skill_is_an_error_not_executed(self):
        bad = self.root / 'bad' / 'SKILL.md'
        bad.parent.mkdir()
        bad.write_text('not front matter', encoding='utf-8')
        result = discover([bad.parent])
        self.assertEqual(result['capabilities'], [])
        self.assertEqual(len(result['errors']), 1)

    def test_v41_invocation_requires_locked_source_and_fixed_adapter_arguments(self):
        with self.assertRaises(DiscoveryError):
            invoke_v41('inventory', self.skill, [], self.root / 'out')

    def test_v41_rejects_unknown_args_before_starting_subprocess(self):
        with patch('rd.registry.subprocess.run') as run:
            with self.assertRaises(DiscoveryError):
                invoke_v41('inventory', self.root, ['--help'], self.root / 'out')
        run.assert_not_called()

    def test_anchor_accepts_only_documented_root_and_deep_flags(self):
        from rd.registry import _safe_args
        self.assertEqual(_safe_args('anchor', ['ledger.json', '--deep', '--root', 'project'], self.root),
                         ['validate', 'ledger.json', '--deep', '--root', 'project'])
        with self.assertRaises(DiscoveryError):
            _safe_args('anchor', ['ledger.json', '--output', 'anything'], self.root)

    def test_planner_output_cannot_escape_output_directory(self):
        from rd.registry import _safe_args
        with self.assertRaises(DiscoveryError):
            _safe_args('planner', ['input.json', '--output', '..\\outside.json'], self.root / 'out')

    def test_runtime_capabilities_distinguish_verified_and_design_only(self):
        result = runtime_capabilities()
        rows = {item['id']: item['availability'] for item in result['capabilities']}
        self.assertEqual(rows['text_delta'], 'VERIFIED_EXECUTABLE')
        self.assertEqual(rows['storm'], 'DESIGN_REFERENCE')
        self.assertEqual(rows['v41_read_only_adapters'], 'AVAILABLE_UNTESTED')

    def test_best_qualified_provider_respects_permissions_and_verification(self):
        providers = [
            {'provider_id': 'host', 'availability': 'HOST_WORKFLOW', 'capabilities': ['frontier'], 'permissions': [], 'network': True},
            {'provider_id': 'pilot', 'availability': 'VERIFIED_EXECUTABLE', 'capabilities': ['frontier'], 'permissions': ['local_read'], 'network': False},
        ]
        result = route_capability('frontier', providers, permissions={'local_read'})
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['provider']['provider_id'], 'pilot')


if __name__ == '__main__':
    unittest.main()
