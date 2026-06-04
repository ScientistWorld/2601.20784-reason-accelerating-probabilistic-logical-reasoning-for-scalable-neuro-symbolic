# Paper's Method

## Key Contribution

REASON is an algorithm-hardware co-design framework for accelerating probabilistic logical reasoning in neuro-symbolic AI systems.

## Approach

At the algorithm level, REASON compiles heterogeneous symbolic and probabilistic kernels into a unified directed acyclic graph. SAT/FOL clauses become literal, OR, and AND nodes; probabilistic circuits become leaf, product, and sum nodes; and HMMs become unrolled sequential message-passing DAGs.

The compiled DAG is then pruned. Logical workloads use implication-graph reachability to remove hidden or redundant literals while preserving satisfiability. Probabilistic circuits and HMMs use probability flow: low-flow mixture branches or low-posterior transitions are removed because they contribute minimally to likelihood.

Finally, REASON regularizes high-fan-in DAG nodes into balanced two-input trees so the graph maps cleanly to tree-based processing elements. The hardware part of the paper implements this representation on a reconfigurable accelerator integrated with GPU execution.

## Main Claims

The primary algorithmic claim is that unified DAG construction plus adaptive pruning preserves reasoning performance while reducing memory footprint, averaging 31.7% savings across ten reported tasks. The primary architecture claim is that a reconfigurable tree-based accelerator provides large speed and energy-efficiency gains over CPU/GPU baselines. This reproduction implements and evaluates the algorithmic claim with machine-independent graph metrics; it does not reproduce silicon synthesis or Accel-Sim hardware results.
