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
