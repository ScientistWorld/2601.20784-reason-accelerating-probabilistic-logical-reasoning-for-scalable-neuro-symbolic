# Problem Definition

## Research Question

Can symbolic and probabilistic reasoning kernels in neuro-symbolic systems be transformed into compact executable graph representations while preserving the reasoning result?

## Why It Matters

Neuro-symbolic systems often spend a large fraction of runtime in non-neural logical or probabilistic inference. A successful solution should reduce the size and irregularity of those reasoning workloads without changing the answer quality, making them more practical to execute on constrained hardware.

## Success Criteria

A solution should accept representative logical, sequential probabilistic, and probabilistic-circuit workloads; produce smaller reasoning graphs or equivalent machine-independent work counts; and preserve logical satisfiability or probabilistic likelihood closely enough that downstream task behavior is maintained.
