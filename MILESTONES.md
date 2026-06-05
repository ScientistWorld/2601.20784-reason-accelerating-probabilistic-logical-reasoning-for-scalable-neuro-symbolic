# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

## Stop Justification
- Completed at milestone `core_claim`.
