# Research Discovery V1.0 design

The supplied development brief authorizes autonomous design, implementation, tests,
installation and GitHub upload. Existing V4.1 remains read-only. New repository
and installed skill are separate; private inventory and research state stay local.

## Decision

Use a Python 3.11+ standard-library control plane and Codex host reasoning. A
standalone autonomous LLM service would add credential/cost dependencies and
duplicate the host. Vendoring AI-Scientist/STORM would import large dependencies
and unsafe execution surfaces. A prompt-only collection cannot enforce evidence,
budgets or execution. The chosen design uses actual host tools and bounded CLI
adapters, with explicit HOST_REQUIRED when reasoning cannot execute in Python.

## Components and contracts

- `core.py`: atomic JSON, locked append-only hash-chain events, immutable protocol
  snapshots, content-addressed evidence with origin/time/hash, validated config.
- `registry.py`: discover real skill files, distinguish workflow-only from audited
  executable adapters; missing/unprobed is never available. No unknown code runs.
- `literature.py`: bounded public Crossref/OpenAlex/Semantic Scholar query adapters,
  raw response capture, metadata normalization, errors and incomplete-search flags.
- `discovery.py`: five structured opportunity routes, distinct candidate contracts,
  ideal-result/prior-art counterargument review, qualitative competition, budgeted
  update decisions; scientific interpretation comes from recorded host work.
- `pilot.py`, `worker.py`, `limits.py`: preregistered CSV comparison and metadata
  pilots in isolated subprocesses; enforce wall time, memory/process and disk
  bounds; immutable inputs, negative/failure/inconclusive outputs all persist.
- `handoff.py`: portable versioned dossier, deep hashes, stage labels and V4.1
  evidence-anchor/experiment-plan compatibility checks through audited local CLIs.
- `cli.py`: runnable commands, stable JSON errors and meaningful exit codes.

No module silently asserts originality, causal identification or publication
readiness. Metadata-only evidence cannot verify source conclusions. Search failure
and missing evidence produce UNVERIFIED/BLOCKED, not novelty. Sampling amendments
create new post-hoc versions and never rewrite a preregistration.

## Acceptance

Run fixed scientific regression cases, resource/error/tamper tests, real online
queries, a frozen-cohort low-cost pilot, full dossier export and actual V4.1
validation. Reproduce offline from a new no-site-packages virtual environment.
Independent host behavioral check must report limitations and preserve negatives.
Install at the requested skill path, validate metadata and entrypoint there, then
upload only reviewed distributable files to a private GitHub repository by default.

## Investigation boundary

Before main implementation consume actual local/external audit reports, including
license, maintenance, source pins and rejected projects. Do not copy private skill
text or code. Reuse installed CLI contracts without changing their implementation.
