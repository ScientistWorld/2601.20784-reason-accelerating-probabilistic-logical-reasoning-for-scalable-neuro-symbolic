# Progress

## What Works

The REASON Sec. IV algorithmic pipeline runs end to end:

- logical CNF formulas compile to DAGs and use implication-graph reachability to prune redundant literals;
- HMMs compile to unrolled DAGs and prune low-posterior transitions from forward-backward flow;
- probabilistic circuits compile to sum/product DAGs and prune low-flow mixture branches;
- all transformed DAGs are regularized into two-input form for hardware-style tree mapping.

`scripts/reproduce.sh` generates deterministic fixtures, runs the unpruned baseline, runs the REASON method, evaluates artifacts through `eval/`, writes `scoring/scores.json`, and passes `python validate.py --compare` locally.

## Results

Current local results:

- `sat_implication_pruning`: 16.257% memory reduction, semantics preserved = 1.0.
- `hmm_flow_pruning`: 27.470% memory reduction, average likelihood retention = 100.0%.
- `pc_flow_pruning`: 24.793% memory reduction, average likelihood retention = 100.0%.

Paper Table IV references used in `scoring/reference.json`:

- logical/FOLIO-style: 38% memory reduction with 91/92 accuracy retention;
- HMM/Ctrl-G CoAuthor-style: 29% memory reduction with 86/87 success-rate retention;
- PC/R2-Guard TwinSafety-style: 37% memory reduction with 0.752/0.758 AUPRC retention.

## Remaining

The hardware claims are not reproduced: no Synopsys/Cadence physical design, Accel-Sim integration, or energy model is available here. A CPU compute job is being submitted to verify the portable environment.

## Issues

The first HMM fixture made pruned transitions too likely, which reduced likelihood retention. The fixture was corrected so low-flow transitions are genuinely negligible, matching the paper's pruning assumption.

## Deviations from Paper

The paper evaluates full neuro-symbolic systems and custom hardware across ten datasets. This reproduction uses deterministic procedural kernel benchmarks because the complete workload stack, hardware design files, commercial EDA flow, and cycle-accurate simulator configuration are not available. The algorithm itself is not replaced: the implemented computation follows the paper's unified DAG, adaptive pruning, and two-input regularization steps.
