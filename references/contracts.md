# Contracts

`Project` persists `project.json`, append-only hash-chained `events.jsonl`,
content-addressed `evidence/`, and immutable `snapshots/`. Evidence has an
origin, kind, acquisition time and SHA-256. `audit` must pass before export.

Candidates contain `id`, `route`, `question`, `significance`, `ideal_result`,
`increment_kind`, `claim`, `prediction`, `falsifier`, at least two `rivals`,
`pilot`, `resources`, `failure_information`, `followup`, `evidence_ids`,
`nearest` and `search_ids`. The accepted increment categories are
`confirmation`, `parameter_change`, `application`, `boundary_evidence`,
`mechanism`, `new_capability`, and `scientific_regularities`.

Search records contain provider, public query, URL, UTC time, HTTP status,
raw-response evidence and `verification: METADATA_ONLY`; they cannot verify a
load-bearing claim. A nearest mapping requires a lawful retained source and
exact line range. `COVERED` means the reviewed mapping covers the stated claim;
`UNVERIFIED` means evidence is insufficient; `PILOT_WORTHY_CONDITIONAL` is a
bounded research decision, not a novelty guarantee.

Pilot registrations freeze the inputs, seed, primary observable, controls,
predictions, stop rule, stage and limits. Every result includes status,
interpretation and raw output/error evidence. `NEGATIVE`, `FAILED` and
`INCONCLUSIVE` are first-class results.

## Full-text claims

`fulltext` evidence is acquired only through an allow-listed HTTPS source with
an explicit lawful-access basis. A `literature_claim` event contains the source
identifier, evidence ID, exact one-based line range, verbatim quote, source and
region SHA-256, relation (`SUPPORTS`, `CONTRADICTS`, `LIMITS` or
`OPEN_PROBLEM`) and an independent checker. A full-text download is never
implied by a metadata record.

## Non-CSV plugins

Plugin protocols contain `id`, `plugin_id`, `stage=PILOT`, `inputs`, `limits`,
`seed`, `stop_rule` and `expected_output`. Only IDs returned by
`rd.plugins.discover_plugins()` can run. The V1.0.1 `text_delta` contract takes
two text evidence IDs and emits line counts plus added, removed and common line
counts. Registration freezes the protocol hash; execution retains stdout,
stderr, failures and the bounded runtime metadata.
