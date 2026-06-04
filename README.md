# Overview

- **Paper ID:** 2601.20784
- **Title:** REASON: Accelerating Probabilistic Logical Reasoning for Scalable Neuro-Symbolic Intelligence
- **Domain:** Neuro-symbolic AI / computer architecture
- **TL;DR:** REASON compiles logical and probabilistic reasoning into unified DAGs, prunes low-value structure, regularizes the graph for tree hardware, and reports large efficiency gains.

## Short Summary

The paper argues that symbolic and probabilistic reasoning stages are a major efficiency bottleneck in neuro-symbolic systems. REASON addresses this with a cross-layer design: algorithmic DAG unification/pruning/regularization, a reconfigurable tree-based accelerator, and GPU-coprocessor integration. The reproduction focuses on the algorithmic layer because full hardware synthesis and cycle-accurate accelerator integration are outside this benchmark environment.

## Key Results

- Table IV reports comparable task performance after algorithm optimization with an average 31.7% memory reduction.
- The hardware evaluation reports about 50.65x speedup over Orin NX and 11.98x over RTX GPU, plus two-orders-of-magnitude energy-efficiency gains.
- The accelerator is reported as 6 mm2 and 2.12 W at 28 nm.

---

# Problem Definition

## Research Question

Can symbolic and probabilistic reasoning kernels in neuro-symbolic systems be transformed into compact executable graph representations while preserving the reasoning result?

## Why It Matters

Neuro-symbolic systems often spend a large fraction of runtime in non-neural logical or probabilistic inference. A successful solution should reduce the size and irregularity of those reasoning workloads without changing the answer quality, making them more practical to execute on constrained hardware.

## Success Criteria

A solution should accept representative logical, sequential probabilistic, and probabilistic-circuit workloads; produce smaller reasoning graphs or equivalent machine-independent work counts; and preserve logical satisfiability or probabilistic likelihood closely enough that downstream task behavior is maintained.

---

# Paper's Method

## Key Contribution

REASON is an algorithm-hardware co-design framework for accelerating probabilistic logical reasoning in neuro-symbolic AI systems.

## Approach

At the algorithm level, REASON compiles heterogeneous symbolic and probabilistic kernels into a unified directed acyclic graph. SAT/FOL clauses become literal, OR, and AND nodes; probabilistic circuits become leaf, product, and sum nodes; and HMMs become unrolled sequential message-passing DAGs.

The compiled DAG is then pruned. Logical workloads use implication-graph reachability to remove hidden or redundant literals while preserving satisfiability. Probabilistic circuits and HMMs use probability flow: low-flow mixture branches or low-posterior transitions are removed because they contribute minimally to likelihood.

Finally, REASON regularizes high-fan-in DAG nodes into balanced two-input trees so the graph maps cleanly to tree-based processing elements. The hardware part of the paper implements this representation on a reconfigurable accelerator integrated with GPU execution.

## Main Claims

The primary algorithmic claim is that unified DAG construction plus adaptive pruning preserves reasoning performance while reducing memory footprint, averaging 31.7% savings across ten reported tasks. The primary architecture claim is that a reconfigurable tree-based accelerator provides large speed and energy-efficiency gains over CPU/GPU baselines. This reproduction implements and evaluates the algorithmic claim with machine-independent graph metrics; it does not reproduce silicon synthesis or Accel-Sim hardware results.

---

# Evaluation

## Metrics

`memory_reduction_pct` measures the percentage reduction in graph memory units, where a memory unit is one stored node or one stored edge in the compiled reasoning DAG. Higher is better.

`semantics_preserved` is used for logical workloads and is 1 when the transformed formula preserves satisfiability semantics. Higher is better.

`avg_loglik_retention_pct` is used for probabilistic workloads and is `100 * exp(avg_loglik_after - avg_loglik_before)` over the fixed evaluation sequences or samples. Higher is better, with 100 meaning no likelihood loss.

## Baselines and Targets

The baseline is the unpruned DAG representation of each workload. The target is a transformed graph that reduces memory while retaining logical or probabilistic behavior. Paper-reported algorithm optimization targets from Table IV are used as references: 21% memory reduction with unchanged 81% accuracy for AlphaGeometry/MiniF2F-style logical reasoning, 29% memory reduction with 86/87 success-rate retention for Ctrl-G/CoAuthor-style HMM reasoning, and 37% memory reduction with 0.752/0.758 AUPRC retention for R2-Guard/TwinSafety-style probabilistic reasoning.

## Evaluation Protocol

Run `scripts/reproduce.sh` or run `scripts/baseline.sh`, `scripts/method.sh`, and `scripts/evaluate.sh` in sequence. The method must write `checkpoints/reason_outputs.json`; evaluation reads that artifact plus `checkpoints/baseline_outputs.json` and writes `scoring/scores.json`. Evaluation code must not import the candidate method.

---

# Reproduction Log

### Iteration 1: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 9m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 23:40] - none
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

### [2026-06-04 23:59] - core_claim
- CPU compute job `b5eba0df-eea` completed successfully.
- The container run executed `scripts/run.sh` and passed `python validate.py --compare`.

</details>


---

# Reproduction Milestones

**Current: method_runs**

## Stop Justification
- Completed at milestone `method_runs`.
