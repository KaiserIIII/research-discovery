# V1.0 adoption record

The audit was performed on 2026-10-09 with read-only GitHub REST/HTTP and local
file inspection. Raw responses, hashes and failures remain in the private
workspace audit and are not copied into the distributable skill.

| Source | Verified interface/pin | License observed | V1.0 decision |
|---|---|---|---|
| CS Nature Paper V4.1 | `skill_router.py inventory`, `literature_runtime.py`, `evidence_anchor.py`, `experiment_planner.py`; local commit `4d5c6d00c6af81705e62e783a0b8cabb34313034` | MIT | Read-only thin adapters; never change V4.1 or call arbitrary arguments |
| OpenAlex | public Works query; anonymous smoke 200 | Service terms | Public metadata adapter with limit/retry/error recording |
| Crossref | REST Works/DOI; smoke 200; polite pool expects contact | Service terms | Public metadata adapter; no full-text claim |
| Semantic Scholar | Graph search; anonymous smoke 429 | Service terms | Adapter preserves 429 as error; optional configured key only |
| arXiv | export Atom query; smoke 200 | Service terms | Evidence source reference only; rate limits retained |
| STORM `stanford-oval/storm` | commit `fb951af7744dab086e34962e9bc6fe878e145f83`, `knowledge_storm` | MIT | Process design reference; no dependency |
| AI-Scientist | commit `1de1dbc1f4ee2c5f61e9c94348d55eb51d7fa2eb`, `launch_scientist.py` | Custom AI Scientist Source Code License v1.0 | Do not copy or execute |
| AI-Scientist-v2 | commit `96bd51617cfdbb494a9fc283af00fe090edfae48`, BFTS launcher | Same custom license | Do not copy or execute |
| AlphaGeometry | commit `6777cb586cbb46beed28db12dc72c69770b68337` | Apache-2.0 | Unrelated theorem proving reference |
| BoTorch | commit `da00e04015c0118f1b9383f32cab17bdcc0944ff`, Knowledge Gradient | MIT | Information-gain idea only; no torch dependency |
| Pyro | commit `a31bc1784707268cd79df77ead4c7a47062f0193` | Apache-2.0 | Future probability models only |
| MLflow | commit `6a5bd6c174dcdec4f3f7f0b63962637685fe76f0` | Apache-2.0 | Future tracking integration only |
| DVC | canonical `treeverse/dvc`, commit `56e59829512ff134aa269099a2099587b810b4dd` | Apache-2.0 | Local JSONL evidence is sufficient for V1 |

No external package is installed and no third-party code is vendored. `Sol` and
`Luna` are host roles, not claims that separate model calls happened. Only a
recorded host response can establish that work occurred.
