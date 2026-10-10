# Public literature API conditions

Research Discovery only sends a query to `Crossref`, `OpenAlex`, or `Semantic Scholar` when the caller passes `public_query=True`. The query is URL encoded; local paths, project files, credentials, and unpublished text are never included by the adapter. API keys are not read.

Each attempt is HTTPS-only and restricted to a fixed provider hostname. There are at most three attempts (initial request plus two retries), each with a five-second timeout. Every attempt consumes one `network_requests` budget unit. Response bytes consume the project `max_download_bytes` budget and are retained in a content-addressed `literature_query` evidence envelope. The envelope records provider, query, URL, timestamp, HTTP status, raw response text, normalized metadata records, and attempt errors. `complete` is always false because metadata search is bounded and does not establish literature completeness.

Returned records have `verification: METADATA_ONLY`. They identify candidate papers; they do not verify full text, source claims, novelty, or publication status. Full text must be obtained and inspected through an authorized host workflow and recorded with `Project.add_evidence`.

The adapter uses Python standard-library `urllib`; no service SDK, login, paid account, or automatic PDF download is used. Service terms, rate limits, and availability still apply. Real network smoke runs must be stored outside the distributable project audit when performed.
