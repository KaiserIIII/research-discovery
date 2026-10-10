# Research Discovery V1.0.1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing Research Discovery skill with portable evidence, honest V4.1 admission boundaries, safer resource accounting, lawful full-text review, host-routed hypothesis generation, an audited non-CSV pilot plugin, and regression/CI evidence.

**Architecture:** Preserve the deterministic local control plane for hashes, budgets, state and rejection decisions. Add a content-addressed dossier package, a text-only full-text evidence adapter, a typed host handoff for deep hypotheses, and a manifest-driven built-in `text_delta` pilot executed by the existing bounded runner. Extend the V4 adapter registry with an explicit read-only admission probe; never call arbitrary skills or third-party code.

**Tech Stack:** Python 3.13 standard library, `unittest`/pytest, urllib HTTPS, subprocess, Windows Job Objects/POSIX rlimit, GitHub Actions.

## Global Constraints

- Existing V1.0 behavior remains compatible and CS Nature Paper V4.1 source files remain unchanged.
- Metadata-only search never verifies full text, novelty, causality, or publication readiness.
- Full text is fetched only from an allow-listed HTTPS host with a recorded lawful access basis and size/time budgets.
- A host model response is recorded only when actual actor/model/artifact provenance is present; no Sol/Luna execution is inferred.
- Plugins are manifest-driven, least-privilege, content-hash checked, and either built-in or explicitly audited; arbitrary user code is never executed.
- Resource limiting is a process governor, not a security sandbox; this limitation is surfaced in every pilot result.
- Discovery and pilot artifacts cannot be silently promoted to V4.1 formal evidence.
- No credentials, private audits, absolute personal paths, or third-party source code are committed.

---

### Task 1: Reproduce P0 failures and add failing tests

**Files:** `tests/test_handoff.py`, `tests/test_limits.py`, new `tests/test_fulltext.py`, `tests/test_plugins.py`, `tests/test_registry.py`, `tests/test_discovery.py`.

- [ ] Add tests showing an exported dossier is invalid when its indexed evidence is absent or moved, and valid after moving the complete package.
- [ ] Add a test with pre-existing bytes in a pilot working directory proving disk accounting measures new bytes only.
- [ ] Add tests for lawful text retrieval, exact-line quote provenance, missing/altered quote rejection, and metadata-only refusal.
- [ ] Add tests for host hypothesis responses requiring three distinct routes and preserving provenance.
- [ ] Add tests for built-in text-delta plugin registration, a real run, malformed input and tamper rejection.
- [ ] Add tests for explicit V4.1 admission probe status and capability status classes.
- [ ] Run the focused tests and observe expected import/behavior failures before implementation.

### Task 2: Make dossier exports portable and auditable

**Files:** `scripts/rd/handoff.py`, `scripts/rd/core.py`, `tests/test_handoff.py`.

- [ ] Export small evidence artifacts into `dossier/evidence/<sha256><suffix>` without duplicating content-addressed bytes; preserve external lawful references as `portable=false` with stable URI, retrieval status and reason.
- [ ] Add artifact-to-claim association and embedded hash verification after any directory move.
- [ ] Keep the self-hash omission explicit while hashing every payload, and report `COMPLETE_PORTABLE`, `PARTIAL_EXTERNAL`, or `INCOMPLETE` instead of unconditional PASS.
- [ ] Reject missing, changed, path-escaping and stale external references.

### Task 3: Implement real V4.1 admission boundary

**Files:** `scripts/rd/registry.py`, `assets/adapters.lock.json`, `scripts/rd/handoff.py`, `tests/test_registry.py`, `tests/test_handoff.py`.

- [ ] Add a locked, read-only `research_state.py` admission probe against a temporary V4.1 project, preserving its exit status and gate findings.
- [ ] Export a typed admission request and classify results as `FORMAT_COMPATIBLE`, `TOOLS_VERIFIED`, `SCIENTIFIC_REVIEW_REQUIRED`, `ACCEPTED`, `REJECTED`, or `NEEDS_EVIDENCE`.
- [ ] Ensure compatibility never calls a PASS result scientific acceptance; record the exact V4 tool command, source hash and output.

### Task 4: Fix resource accounting and add regression evidence

**Files:** `scripts/rd/limits.py`, `tests/test_limits.py`.

- [ ] Replace `before + _tree_size(cwd)` with baseline-aware delta accounting for new and increased files.
- [ ] Preserve timeout/CPU/memory/process-tree behavior and Windows Job Object diagnostics.
- [ ] Run Windows-specific tests on the current host and report any unavailable platform branch separately.

### Task 5: Add lawful full-text evidence workflow

**Files:** new `scripts/rd/fulltext.py`, `scripts/discovery.py`, `references/api-conditions.md`, `tests/test_fulltext.py`.

- [ ] Retrieve only allow-listed open-access text/XML sources under explicit `lawful_access_basis`, HTTPS, timeout, byte and network budgets.
- [ ] Save raw bytes/text as content-addressed evidence with source URI, source identifier, HTTP status, retrieval hash, line count and `FULLTEXT_RETRIEVED` status.
- [ ] Add exact-region quote verification and claim records requiring an independent checker; abstract-only material remains conditional.

### Task 6: Add host-routed deep hypothesis generation and adversarial review

**Files:** `scripts/rd/discovery.py`, `scripts/discovery.py`, `tests/test_discovery.py`, `references/contracts.md`.

- [ ] Add a typed `hypothesis-generation` host request with domain/frontier evidence and a strict output contract.
- [ ] Validate host responses as at least three materially distinct routes with predictions, rivals, falsifiers, minimal pilots, resource bounds, nearest-work fields and actor/model provenance.
- [ ] Preserve post-hoc revisions and add explicit ideal-result counterarguments; no novelty score or publication claim is generated.

### Task 7: Add audited non-CSV pilot plugin

**Files:** new `scripts/rd/plugins.py`, `scripts/rd/plugin_worker.py`, `scripts/rd/plugin_pilot.py`, `scripts/discovery.py`, `tests/test_plugins.py`, `examples/text_delta`.

- [ ] Register a built-in `text_delta` plugin with input/output schema, permissions, environment, resource caps, failure contract and source hash.
- [ ] Run a real text-pair static comparison through the bounded worker, retaining negative/inconclusive/failure results and raw output/error evidence.
- [ ] Reject arbitrary executable paths, unknown plugins, stale inputs, changed permissions and over-budget protocols.

### Task 8: Regression, documentation and CI

**Files:** `.github/workflows/ci.yml`, `CHANGELOG.md`, `README.md`, `SKILL.md`, `docs/v1.0.1-verification.md`, `references/contracts.md`.

- [ ] Add offline CI for unit tests, compile, skill validation and synthetic portable dossier checks.
- [ ] Record positive and negative research regressions, real full-text fixture provenance, non-CSV pilot output, current V4.1 boundary and blocked external providers.
- [ ] Classify every requirement as `VERIFIED`, `PARTIALLY_VERIFIED`, `NOT_IMPLEMENTED`, or `BLOCKED`.

### Task 9: Verify, publish branch and open PR

- [ ] Run full tests, fresh real read-only V4.1 inventory/admission probe, full-text fixture, non-CSV pilot, dossier move/tamper checks and GitHub secret/path scan.
- [ ] Sync the installed skill only after verification, commit in focused changes, push `v1.0.1-hardening`, and create a PR with the verification report.
- [ ] Re-check remote branch and PR state before reporting delivery.
