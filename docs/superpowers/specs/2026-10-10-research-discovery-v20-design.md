# Research Discovery V2.0 Core Design

## Goal

Extend the V1.0.1 evidence ledger with evidence-backed scientific knowledge
relations, a safe non-executing computer-science pilot, deterministic provider
routing, and controlled Sol/V1/V2 evaluation records.

## Boundaries

- V2.0 remains a local Python standard-library control plane.
- External repositories are audited through public GitHub metadata and fixed
  commits; their code is not copied or executed.
- Private library sessions, API credentials, cookies and licensed full text are
  never persisted in the repository or dossier.
- Knowledge graph edges remain conditional on retained evidence.
- Source-analysis pilots parse ASTs only and never import or execute source.
- Evaluation output is descriptive until an independent holdout suite is run.
- CS Nature Paper V4.1 remains an independent reviewer and formal-experiment
  gate.

## Interfaces

`rd.knowledge_graph` stores typed nodes and evidence-backed edges and registers
an immutable graph snapshot in the project event journal.

`rd.pilot_discovery` freezes a source-analysis protocol, parses an immutable
source evidence file with `ast`, records metrics and retains an exploratory-only
result.

`rd.literature` supports Crossref, OpenAlex and Semantic Scholar metadata,
OpenAlex key lookup from environment/local ignored storage, deterministic cache
keys, DOI/provider identity normalization and cross-provider deduplication.

`rd.registry.route_capability` chooses the highest qualified provider permitted
by the caller and returns a deterministic fallback when none is eligible.

`rd.evaluation` records controlled baseline runs and computes descriptive means,
costs and V2-versus-V1 deltas without asserting scientific superiority.

## Acceptance

- Existing V1.0.1 tests remain green.
- New V2 contracts have failing tests before implementation and passing tests
  after implementation.
- At least one real OpenAlex request, one real source-analysis pilot and one
  evaluation comparison are retained locally with redacted credentials.
- Release status reports verified software and explicit scientific limitations.
