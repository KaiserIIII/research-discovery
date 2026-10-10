# V2.0 Third-Party Research Capability Audit

Audit date: 2026-10-10 (Asia/Hong_Kong). Sources were queried through the
GitHub connector. No repository was cloned, copied, installed or executed.

| Project | Fixed source | License observed | Windows execution | Decision | Evidence status |
|---|---|---|---|---|---|
| Future-House/paper-qa | `57e89f7223b0960d5ee5ea048c69e3c47e088572` (`v2026.08.12`) | Apache-2.0 | Requires a separate dependency/runtime audit | Borrow retrieval/evidence ideas; no vendoring | DESIGN_REFERENCE |
| stanford-oval/storm | `e80d9bbea7362141a479940dabb751c1f244e4b6` (`v1.1.0`) | MIT | Not run in this release | Borrow multi-perspective search pattern | DESIGN_REFERENCE |
| AkariAsai/OpenScholar | `0e9b8fb912273d3dae39e593da86e4f6d3bf8de1` (`main` at audit) | Apache-2.0 | Not run in this release | Compare as literature synthesis reference | DESIGN_REFERENCE |
| WecoAI/aideml | `6568c8bc27af51fe90ac83cdc87eb59512e4f527` (`v0.2.2`) | MIT (LICENSE observed) | Unsafe to run arbitrary generated code here | Borrow bounded search and failure retention | DESIGN_REFERENCE |
| microsoft/RD-Agent | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` (`v1.0.0`) | MIT | Not run in this release | Borrow R&D loop ideas; no quant-finance coupling | DESIGN_REFERENCE |
| SakanaAI/AI-Scientist-v2 | `96bd51617cfdbb494a9fc283af00fe090edfae48` (`main` at audit) | Custom Responsible-AI-derived license with manuscript disclosure restrictions | Not integrated | Reject vendoring; license and execution surface require separate review | REJECTED |
| allenai/asta-bench | `36c9bc14a83b95851a4f5c4baaccdde6d1c0cafb` (`v0.5.4`) | Apache-2.0 | Evaluation framework not installed | Use as future external benchmark reference | DESIGN_REFERENCE |
| UKGovernmentBEIS/inspect_ai | `697fde94e2bb08fcba1b3bad65d8c752e1812111` (`main` at audit) | MIT | Not installed | Use as future evaluation adapter reference | DESIGN_REFERENCE |
| zotero/zotero | `e60dc9a57eb8d3d3a4a2ab0df4ff59f21079c963` (`10.0.5` tree) | Desktop distribution license requires component-level review | No local connector executed | Support only user-authorized local read-only import later | DESIGN_REFERENCE |

The only V2 capabilities marked `VERIFIED_EXECUTABLE` are code owned by this
repository and covered by behavior tests: evidence-backed graph registration,
AST-only static analysis, literature normalization/cache and evaluation
recording. A GitHub README or star count is never treated as runtime proof.

## Requested V2 integrations

The audit found no executable integration for PaperQA2/PaperQA, AstaBench,
Inspect AI, or AIDE/AideML in this branch. Their rows above remain
`DESIGN_REFERENCE`; no dependency was installed, no private material was sent
to them, and no capability claim is derived from their documentation. The
local evaluation, bounded AST worker, evidence ledger and provider adapters are
the only behavior-tested implementations in this release.
