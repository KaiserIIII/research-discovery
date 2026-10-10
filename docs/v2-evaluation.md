# V2.0 Evaluation Contract

The evaluation engine records the same case for three baselines:

- `sol_direct`: the host uses the same research tools directly.
- `v1.0.1`: the hardened V1 workflow.
- `v2.0`: the V2 workflow with graph, identity, routing and pilot controls.

Each run stores the case ID, normalized scores in `[0,1]`, observed cost,
allocated budget, actor/model, frozen conditions, and an explicit `real` or
`synthetic` source label. `evaluation-compare` only computes a V2-versus-V1
delta for a unique pair of explicitly real runs with the same case, actor,
conditions and allocated budget. Unmatched runs remain visible as unpaired;
synthetic fixtures are reported separately and never produce an uplift delta.

The resulting delta is descriptive. It does not claim a causal improvement,
publication advantage or general scientific superiority. Those claims require
a historical replay, unseen holdout cases, identical budgets and an
independent review.
