"""Bounded public metadata queries with evidence-bound raw response capture."""
from __future__ import annotations

import html
import io
import json
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


def _papers(provider: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("message", {}).get("items", []) if provider == "crossref" else payload.get("results", []) if provider == "openalex" else payload.get("data", [])
    output = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if provider == "crossref":
            doi = row.get("DOI")
            title = _clean((row.get("title") or [""])[0])
            dates = row.get("published", {}).get("date-parts", [[]])
            year = dates[0][0] if dates and dates[0] else None
            url = row.get("URL") or (f"https://doi.org/{doi}" if doi else "")
            abstract = _clean(row.get("abstract"))
        elif provider == "openalex":
            ids = row.get("ids") or {}
            doi = (ids.get("doi") or "").removeprefix("https://doi.org/") or None
            title, year, url = row.get("title", ""), row.get("publication_year"), row.get("doi") or row.get("id", "")
            abstract, doi = "", doi
        else:
            ids = row.get("externalIds") or {}
            doi, title, year, url, abstract = ids.get("DOI"), row.get("title", ""), row.get("year"), row.get("url", ""), row.get("abstract", "")
        output.append({"id": doi or row.get("id") or url or title, "title": _clean(title), "year": year, "doi": doi, "url": url, "abstract": _clean(abstract), "verification": "METADATA_ONLY"})
    return output


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
    url = template.format(query=urllib.parse.quote(query.strip()), limit=limit)
    attempts: list[dict[str, Any]] = []
    final_status: int | None = None
    raw_text = ""
    payload: dict[str, Any] | None = None
    for attempt in range(3):
        project.consume("network_requests", 1)
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "research-discovery/1.0"})
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
            attempts.append({"attempt": attempt + 1, "http": exc.code, "error": raw_text})
            if overflow:
                attempts[-1]["error"] = "response exceeds download budget"
                break
            if attempt < 2:
                time.sleep(0.01 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, DiscoveryError) as exc:
            attempts.append({"attempt": attempt + 1, "http": final_status, "error": str(exc)})
            if isinstance(exc, DiscoveryError) and "response exceeds download budget" in str(exc):
                raw_text = str(exc)
                break
            if attempt < 2:
                time.sleep(0.01 * (attempt + 1))
            else:
                raw_text = raw_text or str(exc)
    envelope = {"provider": provider, "query": query, "url": url, "timestamp": now(), "http": final_status, "status": final_status or "ERROR", "raw": raw_text, "papers": _papers(provider, payload or {}), "attempts": attempts}
    evidence_id = _evidence(project, envelope)
    papers = envelope["papers"]
    return {"status": "OK" if payload is not None else "ERROR", "query_evidence": evidence_id, "papers": papers, "complete": False, "provider": provider, "query": query, "attempts": attempts, "error": None if payload is not None else "metadata request failed"}
