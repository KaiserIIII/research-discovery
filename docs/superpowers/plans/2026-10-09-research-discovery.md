# Research Discovery V1.0 Implementation Plan

**Goal:** Deliver the installed executable discovery skill and verified GitHub source.
**Architecture:** Standard-library control plane with real Codex host reasoning,
audited local CLI adapters, bounded pilots and portable evidence dossiers.
**Tech stack:** Python 3.11+, unittest, urllib, subprocess, Windows Job Objects.

## Constraints

Never change V4.1 or existing research state. No external code installation,
paid resources, arbitrary untrusted script execution or private data export.
Exploratory outputs remain exploratory. Missing literature cannot prove novelty.

## Tasks

- [ ] 1. Finish actual ecosystem audit, record pins/licenses and adoption decisions.
- [ ] 2. Write contract tests for strict config, evidence tampering, journal integrity,
  five opportunity routes and novelty cases; run the red baseline before implementation.
- [ ] 3. Implement core state and scientific candidate contracts. Run focused unittest.
- [ ] 4. Implement/audit registry and public API adapters with actual bounded calls.
- [ ] 5. Test pilot preregistration, negative/inconclusive/failure/timeout/memory/disk
  behavior before implementing runtime. Freeze input, record environment and seed.
- [ ] 6. Implement dossier export and V4.1 thin adapter; test missing outputs, tamper,
  paths and version mismatch. Run actual V4.1 validation on isolated new files.
- [ ] 7. Connect CLI and concise skill workflow; forward-test using a fresh subagent.
- [ ] 8. Run real three-candidate end-to-end, preserve raw acquisition/run records,
  interpret outputs with limits, reproduce in a new venv and audit requirement coverage.
- [ ] 9. Validate installed skill, publish source + safe public example + accurate
  delivery report, verify GitHub commit and CI. Keep local private audit outside Git.

## Commands and expected behavior

`python -m unittest discover -s tests -v`: all contract cases pass; online-only
cases report real PASS/ERROR/SKIP independently from deterministic fixtures.
`python scripts/discovery.py --help`: exposes runnable operations.
`python scripts/discovery.py doctor`: reports actual platform/resources.
`python scripts/discovery.py validate PROJECT`: rejects altered evidence/protocol.
`python scripts/discovery.py export PROJECT OUTPUT`: complete versioned dossier.
`python scripts/discovery.py compatibility OUTPUT --v41 PATH`: read-only V4.1 checks.

Each stage retains its red/green command output in local validation records.
