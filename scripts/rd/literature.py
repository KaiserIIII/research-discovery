"""Bounded public metadata queries with evidence-bound raw response capture."""
from __future__ import annotations

import html
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .core import DiscoveryError, Project, now

PROVIDERS = {
    "crossref": ("api.crossref.org", "https://api.crossref.org/works?query.bibliographic={query}&rows={limit}"),
    "openalex": ("api.openalex.org", "https://api.openalex.org/works?search={query}&per-page={limit}"),
    "semantic_scholar": ("api.semanticscholar.org", "https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit={limit}&fields=title,year,abstract,externalIds,url"),
}


def _clean(value: Any) -> str:
    return " ".join(html.unescape(str(value or "")).replace("<jats:p>", "").replace("</jats:p>", "").split())


def _normalize_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip().lower()
    doi = re.sub(r"^https?://doi\.org/", "", doi)
    return doi or None


def _canonical_id(provider: str, row: dict[str, Any], doi: str | None, title: str, year: Any) -> str:
    if doi:
        return "doi:" + doi
    if provider == "openalex" and row.get("id"):
        return "openalex:" + str(row["id"]).rstrip("/").split("/")[-1].lower()
    if provider == "semantic_scholar" and row.get("paperId"):
        return "s2:" + str(row["paperId"]).lower()
    normalized = re.sub(r"\W+", " ", title.lower()).strip()
    return "title:" + normalized + ":" + str(year or "")


def _openalex_abstract(row: dict[str, Any]) -> str:
    inverted = row.get("abstract_inverted_index")
    if not isinstance(inverted, dict):
        return ""
    words = []
    for word, positions in inverted.items():
        for position in positions if isinstance(positions, list) else []:
            words.append((position, word))
    return _clean(" ".join(word for _, word in sorted(words)))


def _papers(provider: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("message", {}).get("items", []) if provider == "crossref" else payload.get("results", []) if provider == "openalex" else payload.get("data", [])
    output = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if provider == "crossref":
            doi = _normalize_doi(row.get("DOI"))
            title = _clean((row.get("title") or [""])[0])
            dates = row.get("published", {}).get("date-parts", [[]])
            year = dates[0][0] if dates and dates[0] else None
            url = row.get("URL") or (f"https://doi.org/{doi}" if doi else "")
            abstract = _clean(row.get("abstract"))
        elif provider == "openalex":
            ids = row.get("ids") or {}
            doi = _normalize_doi(ids.get("doi") or row.get("doi"))
            title, year, url = row.get("title", ""), row.get("publication_year"), row.get("doi") or row.get("id", "")
            abstract = _openalex_abstract(row)
        else:
            ids = row.get("externalIds") or {}
            doi, title, year, url, abstract = _normalize_doi(ids.get("DOI")), row.get("title", ""), row.get("year"), row.get("url", ""), row.get("abstract", "")
        clean_title = _clean(title)
        output.append({"id": doi or row.get("id") or url or title, "canonical_id": _canonical_id(provider, row, doi, clean_title, year),
                       "provider": provider, "title": clean_title, "year": year, "doi": doi, "url": url,
                       "abstract": _clean(abstract), "verification": "METADATA_ONLY"})
    return output


def merge_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate normalized records while retaining the most informative row."""
    merged: dict[str, dict[str, Any]] = {}
    for paper in papers:
        key = paper.get("canonical_id") or paper.get("id")
        if not key:
            continue
        current = merged.get(key)
        if current is None:
            merged[key] = dict(paper)
            continue
        for field, value in paper.items():
            if value not in (None, "", []) and current.get(field) in (None, "", []):
                current[field] = value
    return sorted(merged.values(), key=lambda row: (-(row.get("year") or 0), row.get("canonical_id", "")))


def _openalex_key() -> tuple[str | None, str]:
    value = os.environ.get("OPENALEX_API_KEY", "").strip()
    if value:
        return value, "environment"
    configured = os.environ.get("RD_OPENALEX_KEY_FILE", "").strip()
    paths = [Path(configured)] if configured else []
    paths.append(Path.home() / ".codex" / "skills" / "research-discovery" / ".secrets" / "openalex.json")
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            value = str(data.get("api_key") or data.get("openalex_api_key") or data.get("key") or "").strip()
            if value:
                return value, "local_file"
    return None, "none"


def _redact(value: Any, secret: str | None) -> str:
    text = str(value or "")
    return text.replace(secret, "[REDACTED]") if secret else text


def _cache_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _evidence(project: Project, envelope: dict[str, Any]) -> str:
    path = project.root / "runs" / f"literature-{int(time.time_ns())}.json"
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        try:
            return project.add_evidence(path, envelope.get("url", "public metadata API"), "literature_query")
        except DiscoveryError:
            # A fully exhausted artifact budget cannot store even the JSON envelope.
            # Preserve the query result while reporting the missing evidence id.
            return ""
    finally:
        path.unlink(missing_ok=True)


def _read_response(response: Any, cap: int) -> tuple[bytes, int, dict[str, str], bool]:
    headers = {str(k).lower(): str(v) for k, v in getattr(response, "headers", {}).items()}
    status = int(getattr(response, "status", getattr(response, "code", 200)))
    raw = response.read(cap + 1)
    return raw[:cap], status, headers, len(raw) > cap


def search(project: Project, provider: str, query: str, limit: int = 5, public_query: bool = False) -> dict[str, Any]:
    if not public_query:
        return {"status": "ERROR", "error": "public_query=True is required", "query_evidence": None, "papers": [], "complete": False}
    if provider not in PROVIDERS:
        return {"status": "ERROR", "error": "unknown provider", "query_evidence": None, "papers": [], "complete": False}
    if not isinstance(query, str) or not query.strip() or not isinstance(limit, int) or not 1 <= limit <= 50:
        return {"status": "ERROR", "error": "invalid query or limit", "query_evidence": None, "papers": [], "complete": False}
    host, template = PROVIDERS[provider]
    safe_url = template.format(query=urllib.parse.quote(query.strip()), limit=limit)
    secret, key_source = _openalex_key() if provider == "openalex" else (None, "none")
    url = safe_url + ("&api_key=" + urllib.parse.quote(secret) if provider == "openalex" and secret else "")
    cache_key = hashlib.sha256(f"{provider}\n{query.strip().lower()}\n{limit}".encode("utf-8")).hexdigest()
    cache_path = project.root / "runs" / ("literature-cache-" + cache_key + ".json")
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cache_stamp = cache_path.with_suffix(cache_path.suffix + ".sha256")
        cache_valid = cache_stamp.read_text(encoding="ascii").strip() == _cache_digest(cache_path)
    except (OSError, ValueError, UnicodeError):
        cached, cache_valid = None, False
    if cache_valid and isinstance(cached, dict) and cached.get("provider") == provider and cached.get("query") == query:
        evidence_id = _evidence(project, cached)
        return {"status": "OK" if cached.get("payload_ok") else "ERROR", "query_evidence": evidence_id,
                "papers": cached.get("papers", []), "complete": False, "provider": provider, "query": query,
                "attempts": cached.get("attempts", []), "cache_hit": True, "error": cached.get("error")}
    attempts: list[dict[str, Any]] = []
    final_status: int | None = None
    raw_text = ""
    payload: dict[str, Any] | None = None
    for attempt in range(3):
        project.consume("network_requests", 1)
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "research-discovery/2.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                remaining_bytes = int(project.remaining("max_download_bytes"))
                raw, status, _, overflow = _read_response(response, remaining_bytes)
            # Reserve envelope/diagnostic bytes in the aggregate acquisition
            # budget; a tiny remaining budget must fail before treating a
            # truncated metadata response as a valid search.
            if overflow or len(raw) + 64 > remaining_bytes:
                project.consume("max_download_bytes", remaining_bytes)
                raise DiscoveryError("response exceeds download budget")
            project.consume("max_download_bytes", len(raw))
            final_status, raw_text = status, raw.decode("utf-8", errors="replace")
            attempts.append({"attempt": attempt + 1, "http": status, "error": None})
            if status >= 400:
                raise urllib.error.HTTPError(url, status, "HTTP error", {}, io.BytesIO(raw))
            payload = json.loads(raw_text)
            break
        except urllib.error.HTTPError as exc:
            final_status = exc.code
            remaining_error_bytes = int(project.remaining("max_download_bytes"))
            error_bytes = exc.read(remaining_error_bytes + 1) if getattr(exc, "fp", None) else b""
            overflow = len(error_bytes) > remaining_error_bytes
            error_bytes = error_bytes[:remaining_error_bytes]
            project.consume("max_download_bytes", len(error_bytes))
            body = error_bytes.decode("utf-8", errors="replace")
            raw_text = body or raw_text
            attempts.append({"attempt": attempt + 1, "http": exc.code, "error": _redact(raw_text, secret)})
            if overflow:
                attempts[-1]["error"] = "response exceeds download budget"
                break
            if attempt < 2:
                time.sleep(0.01 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, DiscoveryError) as exc:
            attempts.append({"attempt": attempt + 1, "http": final_status, "error": _redact(exc, secret)})
            if isinstance(exc, DiscoveryError) and "response exceeds download budget" in str(exc):
                raw_text = str(exc)
                break
            if attempt < 2:
                time.sleep(0.01 * (attempt + 1))
            else:
                raw_text = raw_text or str(exc)
    papers = _papers(provider, payload or {})
    envelope = {"provider": provider, "query": query, "url": safe_url, "timestamp": now(), "http": final_status,
                "status": final_status or "ERROR", "raw": _redact(raw_text, secret), "papers": papers,
                "attempts": attempts, "payload_ok": payload is not None, "api_key_source": key_source,
                "cache_key": cache_key, "error": None if payload is not None else "metadata request failed"}
    cache_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cache_path.with_suffix(cache_path.suffix + ".sha256").write_text(_cache_digest(cache_path) + "\n", encoding="ascii")
    evidence_id = _evidence(project, envelope)
    return {"status": "OK" if payload is not None else "ERROR", "query_evidence": evidence_id, "papers": papers, "complete": False, "provider": provider, "query": query, "attempts": attempts, "cache_hit": False, "error": None if payload is not None else "metadata request failed"}
