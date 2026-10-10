# Research Discovery V2.0 Architecture

```mermaid
flowchart TD
  U[Research task] --> D[Discovery Director / bounded journal]
  D --> R[Capability Registry & Router]
  R --> L[Literature Intelligence]
  R --> G[Evidence-backed Knowledge Graph]
  R --> H[Hypothesis routes and adversarial prior-art review]
  H --> P[Preregistered pilots]
  P --> S[AST-only static analysis or V1 bounded pilot]
  D --> E[Sol / V1 / V2 evaluation records]
  L --> G
  G --> X[Portable dossier]
  E --> X
  X --> V[V4.1 independent admission]
```

The journal and evidence ledger remain the source of integrity. The graph
stores claims and relationships with evidence IDs. The router chooses an
available, permission-compatible provider but has no scientific truth
authority. Pilot outputs remain exploratory and are never copied into formal
V4.1 samples automatically.
