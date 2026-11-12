# Scoring Targets

Scores come from `scripts/evaluate_test.sh` (hidden instances) and are mirrored on the public train slice by `scripts/evaluate_train.sh`.  Metric definitions: `briefing/evaluation.md`.

| Experiment (weight) | Metric | Direction | Coefficient |
|---|---|---|---|
| `sat_implication_pruning` (0.30) | `memory_reduction_pct` (two-input DAG memory, equivalence-gated) | higher | 1.0 |
| `hmm_flow_pruning` (0.35) | `ll_retention_pct_mem40` | higher | 1.0 |
| | `ll_retention_pct_mem30` | higher | 1.0 |
| | `ll_retention_pct_mem20` | higher | 1.0 |
| `pc_flow_pruning` (0.35) | `ll_retention_pct_mem20` | higher | 1.0 |
| | `ll_retention_pct_mem15` | higher | 1.0 |
| | `ll_retention_pct_mem12` | higher | 1.0 |

Constraints that gate every score (failure → worst value in every metric of every experiment): logical equivalence of CNF outputs; proper, normalised HMMs; smooth, decomposable, normalised circuits over the same variables; every model within its evaluator-fixed memory budget; the procedure completes and writes well-formed output for every instance.

Reference (paper's procedure, `reason_algorithm`) and baseline (`magnitude_pruning`) values are in `scoring/scores_test.json` / `scoring/scores_train.json`.
