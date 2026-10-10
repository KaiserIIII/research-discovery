"""Lawful, bounded text/XML retrieval and exact-region claim provenance.

The adapter intentionally does not download arbitrary PDFs or bypass access
controls. It records metadata-only failures and requires a lawful access basis.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import re
import html

from .core import DiscoveryError, Project, contained, now

ALLOWED_HOSTS = {
    'arxiv.org', 'export.arxiv.org', 'ar5iv.labs.arxiv.org',
    'pmc.ncbi.nlm.nih.gov', 'europepmc.org', 'www.ebi.ac.uk'
}
LAWFUL_BASES = {'open_access', 'user_provided_licensed', 'licensed'}


def _host_allowed(uri):
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != 'https' or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host in ALLOWED_HOSTS or any(host.endswith('.' + parent) for parent in ALLOWED_HOSTS)


def _read_response(response, cap):
    raw = response.read(cap + 1)
    headers = {str(k).lower(): str(v) for k, v in getattr(response, 'headers', {}).items()}
    status = int(getattr(response, 'status', getattr(response, 'code', 200)))
    return raw[:cap], status, headers, len(raw) > cap


def _section_index(text):
    """Return conservative line locations for common paper sections."""
    labels = {}
    pattern = re.compile(r"^\s*(methods?|materials\s+and\s+methods|results?|limitations?|discussion|open\s+questions?)\s*:?\s*$", re.I)
    for number, line in enumerate(text.splitlines(), 1):
        plain = html.unescape(re.sub(r"<[^>]+>", " ", line))
        match = pattern.match(plain) or pattern.search(plain)
        if match:
            labels.setdefault(match.group(1).lower().replace(' ', '_'), number)
    return labels


def _html_section_index(text):
    """Find section headings in common HTML heading tags without executing markup."""
    labels = {}
    tag_pattern = re.compile(r"<(?:h[1-6]|div)[^>]*>(.*?)</(?:h[1-6]|div)>", re.I | re.S)
    heading_pattern = re.compile(r"^\s*(?:\d+(?:\.\d+)*\s+)?(introduction|methods?|materials\s+and\s+methods|results?|limitations?|discussion|open\s+questions?)\s*:?\s*$", re.I)
    for match in tag_pattern.finditer(text):
        plain = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
        heading = heading_pattern.match(re.sub(r"\s+", " ", plain))
        if heading:
            label = heading.group(1).lower().replace(' ', '_')
            labels.setdefault(label, text[:match.start()].count('\n') + 1)
    return labels


def retrieve_fulltext(project: Project, source_id: str, source_uri: str, *,
                      lawful_access_basis: str, timeout: float = 8.0):
    if not source_id or not isinstance(source_id, str):
        raise DiscoveryError('A stable source identifier is required')
    if lawful_access_basis not in LAWFUL_BASES:
        raise DiscoveryError('Full text needs a recorded lawful access basis')
    if not _host_allowed(source_uri):
        raise DiscoveryError('Full text URI is not an approved HTTPS host')
    if timeout <= 0 or timeout > 30:
        raise DiscoveryError('Full text timeout is outside the bounded range')
    project.consume('network_requests', 1)
    remaining = int(project.remaining('max_download_bytes'))
    if remaining <= 0:
        raise DiscoveryError('Download budget exhausted')
    request = urllib.request.Request(source_uri, headers={
        'Accept': 'text/plain, text/xml, application/xml, text/html;q=0.8',
        'User-Agent': 'research-discovery/1.0 fulltext-review'
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw, status, headers, overflow = _read_response(response, remaining)
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode('utf-8', errors='replace') if exc.fp else ''
        project.record('fulltext_retrieval', dict(source_id=source_id, source_uri=source_uri,
                      status='ERROR', http=exc.code, lawful_access_basis=lawful_access_basis,
                      error=body or str(exc)))
        raise DiscoveryError(f'Full text provider returned HTTP {exc.code}') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        project.record('fulltext_retrieval', dict(source_id=source_id, source_uri=source_uri,
                      status='ERROR', http=None, lawful_access_basis=lawful_access_basis, error=str(exc)))
        raise DiscoveryError('Full text retrieval failed: ' + str(exc)) from exc
    if overflow or len(raw) + 256 > remaining:
        project.consume('max_download_bytes', remaining)
        raise DiscoveryError('Full text exceeds download budget')
    project.consume('max_download_bytes', len(raw))
    content_type = headers.get('content-type', '').lower()
    if 'pdf' in content_type or raw.startswith(b'%PDF'):
        project.record('fulltext_retrieval', dict(source_id=source_id, source_uri=source_uri,
                      status='UNSUPPORTED_BINARY', http=status, content_type=content_type,
                      lawful_access_basis=lawful_access_basis,
                      reason='PDF bytes require an authorized local extraction workflow'))
        raise DiscoveryError('PDF full text is retained only through an authorized extraction workflow')
    text = raw.decode('utf-8', errors='replace')
    if not text.strip():
        raise DiscoveryError('Full text response is empty')
    temporary = project.root / 'runs' / ('fulltext-' + hashlib.sha256(raw).hexdigest() + '.txt')
    temporary.write_text(text, encoding='utf-8')
    try:
        evidence_id = project.add_evidence(temporary, source_uri, 'fulltext')
    finally:
        temporary.unlink(missing_ok=True)
    lines = text.splitlines()
    entry = dict(source_id=source_id, source_uri=source_uri, evidence_id=evidence_id,
                 status='FULLTEXT_RETRIEVED', http=status, content_type=content_type,
                 lawful_access_basis=lawful_access_basis, source_sha256=hashlib.sha256(raw).hexdigest(),
                 line_count=len(lines), sections=(_section_index(text) or _html_section_index(text)), retrieved_utc=now())
    project.record('fulltext_retrieval', entry)
    return entry


def verify_region(project: Project, evidence_id: str, source_id: str, claim_id: str,
                  start_line: int, end_line: int, quote: str, *, checker: str,
                  relation: str = 'SUPPORTS'):
    if project.audit():
        raise DiscoveryError('Evidence integrity audit failed')
    if not checker or checker == 'host':
        raise DiscoveryError('An independent checker is required for a verified region')
    entry = project.evidence().get(evidence_id)
    if not entry or entry.get('kind') not in {'fulltext', 'public_primary_source'}:
        raise DiscoveryError('Evidence is not a retrievable full-text artifact')
    path = contained(project.root, entry['path'])
    retrievals = [event['payload'] for event in project.events() if event['kind'] == 'fulltext_retrieval'
                  and event['payload'].get('evidence_id') == evidence_id
                  and event['payload'].get('status') == 'FULLTEXT_RETRIEVED']
    if retrievals and all(item.get('source_id') != source_id for item in retrievals):
        raise DiscoveryError('Source identifier does not match the retained full text')
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    if not isinstance(start_line, int) or not isinstance(end_line, int) or start_line < 1 or end_line < start_line or end_line > len(lines):
        raise DiscoveryError('Exact source region is outside the artifact')
    material = '\n'.join(lines[start_line - 1:end_line])
    if material != quote:
        raise DiscoveryError('Quoted region does not exactly match the retained artifact')
    if relation not in {'SUPPORTS', 'CONTRADICTS', 'LIMITS', 'OPEN_PROBLEM'}:
        raise DiscoveryError('Unknown evidence relation')
    region_sha256 = hashlib.sha256(material.encode('utf-8')).hexdigest()
    record = dict(source_id=source_id, claim_id=claim_id, evidence_id=evidence_id,
                  relation=relation, exact_region=f'lines {start_line}-{end_line}',
                  quote=quote, region_sha256=region_sha256,
                  source_sha256=entry['sha256'], checker=checker,
                  verification_status='VERIFIED', verified_utc=now())
    project.record('literature_claim', record)
    return dict(status='VERIFIED', **record)
