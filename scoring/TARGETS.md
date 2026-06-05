# Scoring Targets

Optimize the fixed three-kernel benchmark:

- `sat_implication_pruning`: increase pruning and final two-input DAG compression while keeping `semantics_preserved` and `implication_proof_sound` at 1.
- `hmm_flow_pruning`: increase pruning and final two-input DAG compression while keeping likelihood-retention metrics close to the uncompressed baseline.
- `pc_flow_pruning`: increase pruning and final two-input DAG compression while keeping likelihood-retention metrics close to the uncompressed baseline.

Every submitted method must write the same artifact schema consumed by `scripts/evaluate.sh`.
