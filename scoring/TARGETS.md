# Scoring Targets

Optimize the fixed three-kernel benchmark:

- `sat_implication_pruning`: increase graph compression metrics while keeping `semantics_preserved` at 1.
- `hmm_flow_pruning`: increase graph compression metrics while keeping likelihood-retention metrics close to the uncompressed baseline.
- `pc_flow_pruning`: increase graph compression metrics while keeping likelihood-retention metrics close to the uncompressed baseline.

Every submitted method must write the same artifact schema consumed by `scripts/evaluate.sh`.
