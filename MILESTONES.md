# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-04 23:58] - none
- Read the paper and identified REASON's reproducible algorithmic core: unified DAG construction, adaptive pruning, and two-input regularization.

### [2026-06-04 23:43] - method_runs
- Implemented SAT/FOL implication pruning, HMM posterior-flow pruning, probabilistic-circuit flow pruning, and DAG regularization.
- Added baseline and method scripts that execute end to end and write reusable artifacts.

### [2026-06-04 23:47] - core_claim
- Local `scripts/reproduce.sh` run passed validation.
- Reproduced the core algorithmic claim on deterministic logical, HMM, and probabilistic-circuit benchmarks: smaller DAGs with preserved semantics or likelihood.

### [2026-06-04 23:55] - core_claim
- Fixed contained-job import failure from CPU job `7c42e167-2a5` by making scripts export `PYTHONPATH=/home/user` and adding package markers.
- Verified `scripts/run.sh` with a stripped local environment.

## Stop Justification
- Not stopped. A CPU compute job is being submitted to validate the packaged pipeline.
