# Public literature API conditions

Research Discovery only sends a query to `Crossref`, `OpenAlex`, or `Semantic Scholar` when the caller passes `public_query=True`. The query is URL encoded; local paths, project files, credentials, and unpublished text are never included by the adapter. API keys are not read.

Each attempt is HTTPS-only and restricted to a fixed provider hostname. There are at most three attempts (initial request plus two retries), each with a five-second timeout. Every attempt consumes one `network_requests` budget unit. Response bytes consume the project `max_download_bytes` budget and are retained in a content-addressed `literature_query` evidence envelope. The envelope records provider, query, URL, timestamp, HTTP status, raw response text, normalized metadata records, and attempt errors. `complete` is always false because metadata search is bounded and does not establish literature completeness.

Returned records have `verification: METADATA_ONLY`. They identify candidate papers; they do not verify full text, source claims, novelty, or publication status. Full text must be obtained and inspected through an authorized host workflow and recorded with `Project.add_evidence`.

The adapter uses Python standard-library `urllib`; no service SDK, login, paid account, or automatic PDF download is used. Service terms, rate limits, and availability still apply. Real network smoke runs must be stored outside the distributable project audit when performed.

## Full text

The full-text adapter is a separate, bounded workflow. It accepts HTTPS only
from the explicit arXiv/PMC host allowlist and requires `open_access`,
`user_provided_licensed`, or `licensed` as the access basis. It requests text,
XML or HTML and refuses PDF bytes because no access-control bypass or implicit
PDF extraction is provided. Each request consumes the project network and byte
budgets. Retrieved text becomes content-addressed `fulltext` evidence, and a
claim is load-bearing only after `verify_region` records an exact line range,
verbatim quote, relation and independent checker.
