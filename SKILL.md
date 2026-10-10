---
name: research-discovery
description: Use when a researcher needs evidence-bound problem discovery, nearest-work novelty challenge, competing hypotheses, a bounded exploratory pilot, or a machine-readable handoff to CS Nature Paper V4.1.
metadata:
  short-description: Evidence-bound research discovery and pilots
---

# Research Discovery V2.0 Candidate

Run `python scripts/discovery.py --help` from this skill directory. This skill
coordinates host capabilities and deterministic local records; it does not act
as an autonomous paper author, originality oracle, publication predictor, or
formal experiment system.

## Operating contract

1. Inspect the actual host and local capabilities before choosing work. A
   `SKILL.md`, catalog entry, search hit, or model role is not an execution.
2. Create a private project with `init`. Keep the domain, configuration,
   evidence, protocol, event journal and failures in the project directory.
3. Gather a frontier packet using approved public providers or an actual host
   request. Record query, raw response, provider, date, HTTP status, retries and
   incomplete coverage. Do not send local code, secrets or private documents.
4. Use `mine` to produce the contradiction, boundary, transfer, failure and
   mechanism routes. Supply at least three materially different candidates to
   `admit`. Every candidate needs rivals, falsifier, concrete prediction,
   resource limits, nearest work and a minimal discriminating pilot.
5. Treat metadata and abstracts as `METADATA_ONLY`; a search miss is
   `UNVERIFIED`. For a load-bearing nearest-work relation, a locally retained
   lawful source, exact line region, quoted text, relation, objection and
   unresolved item are required. The result is still conditional review.
6. Register the pilot before execution. Pilot data, failures, timeouts and
   negative outcomes are retained. A post-hoc interpretation receives a new
   `EXPLORATORY_POST_HOC` identity and cannot rewrite the registered prediction.
7. Stop when integrity, resource budgets, evidence coverage or scientific value
   requires it. Ask the host for Sol/Luna work with `host-request`; only an
   actual response with artifact IDs may be recorded, and it never qualifies
   itself as an independent checker.
8. For deep semantic work, use `hypotheses-request` and require an actual
   host response with a request hash, actor/model, findings, artifact IDs and
   at least three materially distinct candidates. A host response is recorded
   as requiring admission; it is not an originality verdict.
9. Full text may be retrieved only from the HTTPS allowlist with a recorded
   lawful access basis. Verify load-bearing claims with exact line ranges and
   an independent checker. Metadata and abstracts remain `METADATA_ONLY`.
10. Export and validate the dossier. `handoff_to_v4_1.md` explicitly leaves
   scientific authority with V4.1; V4.1 must independently review novelty,
   feasibility, protocol, statistics, reproducibility and publication sufficiency.

## V2.0 core additions

- `knowledge-graph-validate/register` validates typed Paper/Claim/Hypothesis,
  Method/Dataset/Result relations and requires retained evidence on every edge.
- Literature search normalizes DOI/provider identities, deduplicates records,
  caches repeat queries and reads OpenAlex credentials only from the environment
  or ignored local secret storage. Keys are never placed in evidence envelopes.
- `static-analysis-register/run` performs a preregistered AST-only pilot on
  immutable source evidence. It never imports or executes source and reports
  `EXPLORATORY_ONLY`.
- `evaluation-record/compare` records controlled direct-Sol, V1 and V2 runs;
  descriptive deltas do not establish scientific superiority.

## Safety and limits

The bundled pilot runner executes built-in CPU analysis and the audited
non-CSV `text_delta` plugin. It is bounded, not a security sandbox; it cannot
promise OS, network or native-code isolation. Never run untrusted packages,
use paid cloud resources, mutate V4.1, or mix discovery/pilot outputs into
formal samples.

Read `references/contracts.md` for schemas and `references/ecosystem.md` for
the actual adoption and rejection audit. Local private audit files stay outside
the distributable skill. Use `examples/` only as safe synthetic fixtures.
