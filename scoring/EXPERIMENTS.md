# Experiments

`sat_implication_pruning` tests whether a logical reasoning workload can be represented more compactly without changing the formula semantics. It scores both reduced graph size and final graph size after the same two-input normalization is applied to the unpruned baseline.

`hmm_flow_pruning` tests whether a sequential probabilistic workload can be represented more compactly while retaining sequence likelihood. It scores both reduced graph size and final graph size after the same two-input normalization is applied to the unpruned baseline.

`pc_flow_pruning` tests whether a probabilistic mixture/circuit workload can be represented more compactly while retaining sample likelihood. It scores both reduced graph size and final graph size after the same two-input normalization is applied to the unpruned baseline.
