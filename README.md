# Research Discovery V1.0

This is an evidence-bound Codex Skill for finding and testing research
questions. It records actual public metadata searches, competing explanations,
pre-registered bounded pilots, negative results and a portable handoff to CS
Nature Paper V4.1. It never claims that a search proves originality or that a
pilot is a formal experiment.

```powershell
cd C:\Users\17271\.codex\skills\research-discovery
python scripts/discovery.py doctor
python scripts/discovery.py init projects\demo --domain "software measurement"
python scripts/discovery.py mine examples\seed.json --output projects\demo\opportunities.json
python scripts/discovery.py registry C:\Users\17271\.codex\skills --output projects\demo\capabilities.json
python scripts/discovery.py search projects\demo --provider crossref --query "reproducible Python package builds" --public
python -m unittest discover -s tests -v
```

For three candidates, create a JSON list following `references/contracts.md` and
run `admit`. Export with `export`; verify with `validate` and inspect
`handoff_to_v4_1.md`. A search needs `--public`, uses only an allow-listed
provider and stores a metadata-only envelope. Configure a real contact address
for Crossref outside this repository if its polite-pool policy requires it.

`examples/dossier/` is a generated synthetic handoff showing three competing
routes and a retained negative pilot. Its result is deliberately exploratory.

The bundled pilot runner is deliberately CPU-only and uses no third-party
packages. It applies bounded time, memory and disk/process controls where the
host permits them, but remains a resource governor rather than a security
sandbox. Do not execute untrusted packages or source files.

The private ecosystem and API audit that supports adoption decisions is kept
outside this distributable repository at `E:\final\research-discovery-audit`.
