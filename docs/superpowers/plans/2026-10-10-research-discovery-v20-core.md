# Research Discovery V2.0 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the evidence-backed V2.0 core without importing unverified external runtimes.

**Architecture:** Keep V1.0.1's append-only journal, immutable evidence and bounded pilots. Add focused standard-library modules for graph provenance, source-only analysis, provider routing, literature identity/cache, and controlled evaluation.

**Tech Stack:** Python 3.11+, standard library, pytest, GitHub public metadata.

## Global Constraints

- Never execute untrusted source or third-party repositories.
- Never persist credentials, cookies, signed library URLs or licensed full text.
- Never turn metadata-only search into a novelty or causal claim.
- Never mark an external capability integrated without a successful behavior test.
- Preserve V4.1 independence and formal sample separation.

### Task 1: Evidence-backed knowledge graph

**Files:** `scripts/rd/knowledge_graph.py`, `tests/test_v2_core.py`

- [x] Define typed nodes and relations.
- [x] Require evidence IDs on every edge.
- [x] Validate and register immutable graph snapshots.

### Task 2: Literature identity, key isolation and cache

**Files:** `scripts/rd/literature.py`, `tests/test_literature.py`

- [x] Read OpenAlex key from environment or ignored local file.
- [x] Keep redacted URLs and error envelopes.
- [x] Add DOI/provider identity normalization and deterministic cache.
- [x] Deduplicate records without discarding richer metadata.

### Task 3: Safe computer-science pilot

**Files:** `scripts/rd/pilot_discovery.py`, `scripts/discovery.py`, `tests/test_v2_core.py`

- [x] Freeze source-analysis protocol and hash.
- [x] Parse AST only and retain exploratory results.
- [x] Reject missing/tampered evidence and repeated execution.

### Task 4: Evaluation and routing

**Files:** `scripts/rd/evaluation.py`, `scripts/rd/registry.py`, `scripts/discovery.py`, `tests/test_registry.py`, `tests/test_v2_core.py`

- [x] Record Sol/V1/V2 scores and bounded cost.
- [x] Compare descriptive means and deltas.
- [x] Route by qualification, permission and verification status.

### Task 5: Audit, documentation and release evidence

**Files:** `docs/third-party-audit-v2.md`, `docs/v2-architecture.md`, `docs/v2-evaluation.md`, `docs/v2-release-status.md`, `README.md`, `CHANGELOG.md`

- [x] Record fixed upstream commits, licenses, behavior status and rejection reasons.
- [x] Record real local runs and limitations.
- [x] Run the complete test and compile checks before publishing a branch.
