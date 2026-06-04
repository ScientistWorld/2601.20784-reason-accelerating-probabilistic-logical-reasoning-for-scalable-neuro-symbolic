# Scoring Targets

Optimize the fixed three-kernel benchmark:

- `sat_implication_pruning`: increase `memory_reduction_pct` while keeping `semantics_preserved` at 1.
- `hmm_flow_pruning`: increase `memory_reduction_pct` while keeping `avg_loglik_retention_pct` close to 100.
- `pc_flow_pruning`: increase `memory_reduction_pct` while keeping `avg_loglik_retention_pct` close to 100.

Every submitted method must write the same artifact schema consumed by `scripts/evaluate.sh`.
