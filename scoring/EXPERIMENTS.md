# Experiments

`sat_implication_pruning` tests whether a logical reasoning workload can be represented more compactly without changing formula semantics. It scores both the reduced graph size and the final executable graph size under the common bounded-local-interface requirement.

`hmm_flow_pruning` tests whether a sequential probabilistic workload can be represented more compactly while retaining sequence likelihood. It scores both the reduced graph size and the final executable graph size under the common bounded-local-interface requirement.

`pc_flow_pruning` tests whether a probabilistic mixture/circuit workload can be represented more compactly while retaining sample likelihood. It scores both the reduced graph size and the final executable graph size under the common bounded-local-interface requirement.
