import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError, Project
from rd.literature import search


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class LiteratureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = Project.create(self.root / 'project', 'test')

    def test_requires_explicit_public_query_before_transport(self):
        with patch('rd.literature.urllib.request.urlopen') as transport:
            result = search(self.project, 'crossref', 'private unpublished query')
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(transport.call_count, 0)
        self.assertEqual(self.project.remaining('network_requests'), 20)

    def test_unknown_provider_is_rejected_without_transport(self):
        with patch('rd.literature.urllib.request.urlopen') as transport:
            result = search(self.project, 'unknown', 'test', public_query=True)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(transport.call_count, 0)

    def test_crossref_normalizes_records_and_saves_metadata_only_evidence(self):
        payload = {'message': {'items': [
            {'DOI': '10.1234/Test', 'title': ['A paper'], 'published': {'date-parts': [[2024]]},
             'URL': 'https://doi.org/10.1234/Test', 'abstract': '<jats:p>Example</jats:p>'}
        ]}}
        with patch('rd.literature.urllib.request.urlopen', return_value=Response(json.dumps(payload).encode())) as transport:
            result = search(self.project, 'crossref', 'test topic', public_query=True)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result['status'], 'OK')
        self.assertFalse(result['complete'])
        paper = result['papers'][0]
        self.assertEqual(paper['title'], 'A paper')
        self.assertEqual(paper['year'], 2024)
        self.assertEqual(paper['verification'], 'METADATA_ONLY')
        self.assertEqual(paper['abstract'], 'Example')
        evidence = self.project.evidence()[result['query_evidence']]
        envelope = json.loads((self.project.root / evidence['path']).read_text(encoding='utf-8'))
        self.assertEqual(evidence['kind'], 'literature_query')
        self.assertEqual(envelope['provider'], 'crossref')
        self.assertEqual(envelope['status'], 200)
        self.assertEqual(self.project.remaining('network_requests'), 19)

    def test_retry_attempts_consume_budget_and_retain_raw_error(self):
        from urllib.error import HTTPError
        error = HTTPError('https://api.crossref.org/works', 429, 'rate limited', {}, io.BytesIO(b'limited'))
        with patch('rd.literature.urllib.request.urlopen', side_effect=error) as transport:
            result = search(self.project, 'crossref', 'test', public_query=True)
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(self.project.remaining('network_requests'), 17)
        evidence = self.project.evidence()[result['query_evidence']]
        envelope = json.loads((self.project.root / evidence['path']).read_text(encoding='utf-8'))
        self.assertEqual(envelope['status'], 429)
        self.assertEqual(envelope['raw'], 'limited')

    def test_request_budget_exhaustion_makes_no_request(self):
        self.project.consume('network_requests', self.project.remaining('network_requests'))
        with patch('rd.literature.urllib.request.urlopen') as transport:
            with self.assertRaises(DiscoveryError):
                search(self.project, 'crossref', 'test', public_query=True)
        self.assertEqual(transport.call_count, 0)

    def test_response_larger_than_remaining_budget_is_recorded_as_error(self):
        self.project.consume('max_download_bytes', self.project.remaining('max_download_bytes') - 10)
        body = json.dumps({'message': {'items': []}}).encode()
        with patch('rd.literature.urllib.request.urlopen', return_value=Response(body)) as transport:
            result = search(self.project, 'crossref', 'test', public_query=True)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(self.project.remaining('max_download_bytes'), 0)

    def test_semantic_scholar_is_normalized_to_metadata_only(self):
        payload = {'data': [{'paperId': 'abc', 'title': 'A study', 'year': 2022,
                             'abstract': 'Summary', 'externalIds': {'DOI': '10.1/a'},
                             'url': 'https://example.test/paper'}]}
        with patch('rd.literature.urllib.request.urlopen', return_value=Response(json.dumps(payload).encode())):
            result = search(self.project, 'semantic_scholar', 'study', public_query=True)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['papers'][0]['doi'], '10.1/a')
        self.assertEqual(result['papers'][0]['verification'], 'METADATA_ONLY')


if __name__ == '__main__':
    unittest.main()
