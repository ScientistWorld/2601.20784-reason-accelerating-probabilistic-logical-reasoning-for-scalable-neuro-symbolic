# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-06-04 23:40] - none
- Started from a partially initialized REASON reproduction workspace.
- Read the paper markdown and identified the reproducible core as the Sec. IV algorithmic flow: unified DAG representation, adaptive pruning, and two-input regularization for SAT/FOL, HMM, and probabilistic-circuit kernels.

### [2026-06-04 23:51] - method_runs
- Implemented and packaged deterministic kernel benchmarks, the unpruned DAG baseline, REASON algorithm passes, and artifact-based evaluation.
- A CPU compute job ran `scripts/reproduce.sh` inside the container and passed `python validate.py --compare`.

### [2026-06-04 23:58] - core_claim
- Reproduced the core algorithmic claim on three reasoning kernels: REASON reduces DAG memory while preserving SAT semantics or probabilistic likelihood fidelity.
- Current reproduced results are 16.257% memory reduction for SAT implication pruning, 27.470% for HMM flow pruning, and 24.793% for PC flow pruning.

### [2026-06-05 00:12] - method_runs
- Continuation audit reset the active milestone to `method_runs`.
- Found and fixed an SAT pruning bug: implication-redundant clauses now remove the implied-covering source literal correctly, and SAT satisfiability preservation is checked instead of hardcoded.
- Local `scripts/reproduce.sh` passes with updated scores: 16.635% SAT memory reduction with satisfiability preserved, 27.470% HMM memory reduction with 100% likelihood retention, and 24.793% PC memory reduction with 100% likelihood retention.
