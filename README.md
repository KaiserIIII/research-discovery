# Research Discovery V2.0 Candidate

This evidence-bound Codex Skill helps researchers find and test research
questions. It records public searches and lawful full text, competing
explanations, preregistered bounded pilots, negative results and a portable
handoff to CS Nature Paper V4.1. A search never proves originality, and a pilot
never becomes a formal experiment by itself.

```mermaid
flowchart LR
    R[Researcher / host model] --> D[Research Discovery control plane]
    D --> L[Public metadata + lawful full text]
    D --> H[Competing hypotheses and adversarial review]
    D --> P[Bounded pilot plugins]
    L --> E[Hash-chained evidence ledger]
    H --> E
    P --> E
    E --> X[Portable Discovery Dossier]
    X --> V[Locked read-only V4.1 adapters]
    V --> G{V4.1 scientific admission}
    G --> A[Accept]
    G --> N[Reject]
    G --> Q[Need evidence]
```

The control plane preserves provenance, budgets, failures and negative results.
The dossier can be moved and independently verified. V4.1 retains authority
over novelty, feasibility, protocol, statistics and publication sufficiency.

```powershell
cd C:\Users\17271\.codex\skills\research-discovery
python scripts/discovery.py doctor
python scripts/discovery.py init projects\demo --domain "software measurement"
python scripts/discovery.py mine examples\seed.json --output projects\demo\opportunities.json
python scripts/discovery.py registry C:\Users\17271\.codex\skills --output projects\demo\capabilities.json
python scripts/discovery.py runtime-capabilities
python scripts/discovery.py search projects\demo --provider crossref --query "reproducible Python package builds" --public
python -m unittest discover -s tests -v
```

For three candidates, create a JSON list following `references/contracts.md` and
run `admit`. Export with `export`; verify with `validate` and inspect
`handoff_to_v4_1.md`. A search needs `--public`, uses only an allow-listed
provider and stores a metadata-only envelope. Configure a real contact address
for Crossref outside this repository if its polite-pool policy requires it.

For a host-generated frontier packet, use `hypotheses-request`. The response
must contain the request hash, actual actor/model, artifact IDs and at least
three materially distinct candidates. It is recorded as
`HOST_GENERATED_REQUIRES_ADMISSION`; it is not automatically admitted as
science.

Full-text retrieval requires a lawful access basis and an HTTPS URL on the
explicit arXiv/PMC allowlist. `fulltext-verify` records an exact line range,
quote, relation, checker and source hash. Abstracts and metadata remain
`METADATA_ONLY`.

The built-in `text_delta` plugin is a bounded non-CSV pilot. Register a JSON
protocol with `plugin-register`, then execute it with `plugin-run`. Its inputs
are content-addressed text evidence and its output and failures are retained
as evidence.

`export` embeds small evidence artifacts in a content-addressed `evidence/`
directory. Larger artifacts require a stable HTTPS origin and are marked
`STABLE_REFERENCE_REQUIRED`; missing or changed evidence makes `validate`
fail. Moving the complete dossier to another directory therefore preserves
the validation root.

`examples/dossier/` is a generated synthetic handoff showing three competing
routes and a retained negative pilot. Its result is deliberately exploratory.

The bundled runners use only the Python standard library and resource
governors. They are not security sandboxes; never execute untrusted packages
or source files.

The private ecosystem and API audit that supports adoption decisions is kept
outside this distributable repository at `E:\final\research-discovery-audit`.

## V2.0 verified core

V2 adds evidence-backed typed knowledge graph edges, deterministic provider
routing, DOI/provider identity normalization with a redacted OpenAlex cache,
and a safe AST-only source-analysis pilot. It also records comparable
`sol_direct`, `v1.0.1` and `v2.0` evaluation runs. These are control-plane
capabilities; they do not prove novelty, causality or scientific superiority.

```powershell
python scripts/discovery.py knowledge-graph-validate graph.json
python scripts/discovery.py static-analysis-register projects\demo protocol.json
python scripts/discovery.py static-analysis-run projects\demo protocol.json
python scripts/discovery.py evaluation-compare projects\demo
```

See `docs/third-party-audit-v2.md`, `docs/v2-architecture.md` and
`docs/v2-release-status.md` for fixed upstream references, integration status
and current scientific limitations.
