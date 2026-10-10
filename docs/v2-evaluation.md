# V2.0 Evaluation Contract

The evaluation engine records the same case for three baselines:

- `sol_direct`: the host uses the same research tools directly.
- `v1.0.1`: the hardened V1 workflow.
- `v2.0`: the V2 workflow with graph, identity, routing and pilot controls.

Each run stores the case ID, normalized scores in `[0,1]`, bounded cost and
actual actor. `evaluation-compare` reports descriptive means and V2-versus-V1
deltas. It does not claim a causal improvement, publication advantage or
general scientific superiority. Those claims require a historical replay,
unseen holdout cases, identical budgets and an independent review.
