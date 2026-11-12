# Overview

- **Paper ID:** 2601.20784
- **Title:** REASON: Accelerating Probabilistic Logical Reasoning for Scalable Neuro-Symbolic Intelligence
- **Domain:** Neuro-symbolic AI / computer architecture
- **TL;DR:** REASON compiles logical and probabilistic reasoning into unified DAGs, prunes low-value structure, regularizes the graph for tree hardware, and reports large efficiency gains.

## Short Summary

The paper argues that symbolic and probabilistic reasoning stages are a major efficiency bottleneck in neuro-symbolic systems. REASON addresses this with a cross-layer design: algorithmic DAG unification/pruning/regularization, a reconfigurable tree-based accelerator, and GPU-coprocessor integration. The reproduction focuses on the algorithmic layer (Sec. IV / Table IV) because full hardware synthesis and cycle-accurate accelerator integration are outside this benchmark environment. The gym scores a method as a procedure run on hidden CNF, HMM and probabilistic-circuit instances: logical outputs must be equivalent (memory reduction is scored), probabilistic outputs must fit evaluator-fixed memory budgets (held-out task likelihood is scored).

## Key Results

- Table IV reports comparable task performance after algorithm optimization with an average 31.7% memory reduction.
- The hardware evaluation reports about 50.65x speedup over Orin NX and 11.98x over RTX GPU, plus two-orders-of-magnitude energy-efficiency gains.
- The accelerator is reported as 6 mm2 and 2.12 W at 28 nm.

---

# Problem Definition

## Research Question

Symbolic and probabilistic reasoning kernels (logical formulas, hidden Markov models, probabilistic circuits) dominate the runtime and memory traffic of many neuro-symbolic systems. Can such a kernel be compiled into a much smaller executable reasoning graph while preserving what it computes for the task it is deployed on?

## Why It Matters

These kernels are irregular, memory-bound graph computations. Every node and edge that survives compilation must be stored and visited on every query, so the size of the compiled graph directly sets memory footprint and runtime on constrained hardware. A useful compression must not change the logical answers, and must keep probabilistic inference accurate on the deployment task's data.

## The Task

A method is a **procedure**. For each kernel instance it receives:

- **CNF logic** (`task = "sat"`): a satisfiable CNF formula over variables `1..n` (a grounded knowledge base: taxonomy implications, typing axioms, disjointness, multi-premise rules, disjunctive facts).
  It must return a CNF formula over the same variables with exactly the same set of satisfying assignments, and as small a compiled graph as possible.
- **HMM** (`task = "hmm"`): a dense hidden Markov model (initial, transition and emission tables) trained for a general domain, a set of *calibration* sequences from the deployment task, the unroll horizon `T`, and three memory budgets.
  For each budget it must return an HMM over the same observation alphabet (any number of states) whose compiled graph fits the budget and which assigns high likelihood to unseen task sequences.
- **Probabilistic circuit** (`task = "pc"`): a smooth, decomposable circuit over binary variables (sum, product and Bernoulli-leaf nodes), calibration samples from the deployment task, and three memory budgets.
  For each budget it must return a valid circuit over the same variables that fits the budget and assigns high likelihood to unseen task samples.

The deployment task's data distribution is related to, but not identical with, the distribution the given HMM or circuit models. Calibration data are the only task data a method sees; scoring uses separate held-out task data.

## Success Criteria

- Logic: equivalent formula with larger memory reduction.
- HMM and PC: higher held-out task likelihood at the same evaluator-fixed memory budgets, without ever exceeding a budget or returning an improper model.

See `briefing/evaluation.md` for the exact accounting, the input/output format and the failure rules.

---

# Paper's Method

## Key Contribution

REASON is an algorithm–hardware co-design framework for accelerating probabilistic logical reasoning in neuro-symbolic AI systems. This gym reproduces its algorithm layer (Sec. IV); the accelerator, GPU integration and timing/energy results (Secs. V–VII-C) are out of scope.

## Approach (as implemented in `method/`)

**Stage 1: unified DAG representation** (`method/reason_dag.py`). Every kernel is compiled into the same DAG abstraction:
- a CNF becomes literal leaves, clause OR nodes and a formula AND node;
- an HMM is unrolled over time steps, with per-state emission sums, sums over predecessor states (transition factors) and products combining the two;
- a probabilistic circuit keeps its sum, product and leaf nodes.

**Stage 2: adaptive pruning** (`method/sat_reason.py`, `method/hmm_reason.py`, `method/pc_reason.py`).
- *Logic*: each binary clause `(l ∨ l')` induces the implications `¬l → l'` and `¬l' → l`. Depth-first reachability over this implication graph gives the "always implied" relation.
  - If `a → b` and both literals are in a clause, `a` is dropped. This is a hidden literal. The paper's prose names the implied literal as the one to drop, but only dropping the implying literal preserves semantics.
  - Failed literals (`l → ¬l`) are removed from every clause.
  - The result is logically equivalent to the input.
- *HMM*: forward–backward on the task's calibration sequences gives the expected (posterior) usage of every transition, emission and initial entry. The entries with the smallest usage are pruned.
- *PC*: the circuit flow of each sum edge is `F_{n,c}(x) = θ_{n,c} p_c(x) / p_n(x) · F_n(x)`, with `F_root = 1` and products passing their flow to every child. Flow is summed over the calibration set, and the sum edges with the smallest cumulative flow are pruned.
- For HMM and PC, pruning removes candidates globally, smallest score first, keeping at least one entry per row or sum node, and stops at the shortest prefix whose compiled DAG fits the memory budget (found by binary search, since memory is monotone). The remaining rows and weights are then renormalised.

**Stage 3: two-input regularisation**. Nodes with fan-in greater than 2 are decomposed into balanced binary trees. This defines the final DAG whose memory (nodes + edges) is measured.

The entry point is `python3 -m method.reason_cli --instance IN.json --out OUT.json`.

## Main Claims

The algorithmic claim (Table IV) is that unified DAG construction plus adaptive pruning and regularisation preserves task performance while reducing memory footprint, by 31.7% on average across ten tasks (21–43% per task). The architecture claims (12–50× speedup, 310–681× energy efficiency over GPUs) are not reproduced here.

## Known limitations of the paper's procedure observed in this gym

- One-shot, flow-ranked pruning degrades at tight budgets. Iterating the flow computation and re-estimating the surviving parameters on the calibration data recovers much of the loss.
- Data-driven HMM pruning can remove every emission of a symbol that is rare in the calibration data, which assigns near-zero probability to task sequences containing it.
- Literal-level implication pruning leaves whole redundant clauses (entailed rules, transitive shortcuts) in place.

---

# Evaluation

## Interface

Register a method with a manifest `checkpoints/<anything>.json`:

```json
{"method": "my_method", "command": ["python3", "-m", "my_package.cli"]}
```

The evaluator runs `<command> --instance IN.json --out OUT.json` once per instance (working directory = repository root, `PYTHONPATH` = repository root, 30-minute limit per call). `IN.json` contains:

| task | fields |
|---|---|
| `sat` | `num_vars`, `clauses` (lists of non-zero ints) |
| `hmm` | `num_states`, `num_symbols`, `horizon`, `initial`, `transition`, `emission`, `calibration` (list of symbol sequences), `budgets`, `budget_fractions`, `reference_memory_units` |
| `pc` | `num_vars`, `circuit` = `{"nodes": [...], "root": i}`, `calibration` (list of `"0101..."` strings), `budgets`, `budget_fractions`, `reference_memory_units` |

Circuit nodes are indexed by list position. Each node is one of `["leaf", var, p]` (Bernoulli, `P(x_var = 1) = p`), `["prod", [children]]` or `["sum", [children], [weights]]`. Every child index must be smaller than its parent's index.

`OUT.json` must be:

- `sat`: `{"clauses": [[...], ...]}`
- `hmm`: `{"models": [{"initial", "transition", "emission"}, ...]}`, with one model per budget, in budget order.
- `pc`: `{"models": [{"nodes", "root"}, ...]}`, with one circuit per budget, in budget order.

Every other field in the output is ignored. The evaluator never reads numbers, flags or statistics that a method reports about itself.

## Memory accounting (computed by the evaluator)

Each model is compiled into a reasoning DAG. Every node with more than two inputs is then expanded into a balanced binary tree of two-input nodes. Memory is the number of nodes plus the number of edges of that final DAG. A node with fan-in `k` costs 1 if `k = 0`, 2 if `k = 1`, and `3(k-1)` otherwise.

- **CNF**: one leaf per distinct literal, one OR node per clause (inputs = its literals), and one AND node over all clauses. Before counting, duplicate literals, tautological clauses and duplicate clauses are removed.
- **HMM**, unrolled over `horizon` steps and counting only states reachable at step `t` (through entries > 0):
  - For each live state, an emission node whose inputs are the observation-indicator leaves of its non-zero emission entries.
  - At `t = 1`, a one-input initial node per live state.
  - At `t > 1`, a sum node over the live predecessors with a non-zero transition, plus a two-input product node (sum × emission).
  - One indicator leaf per symbol used at that step.
  - A root sum over the last step.
- **PC**: the node graph reachable from the root. Zero-weight edges are dropped and single-input sum/product nodes are collapsed (they are identities). Unreachable nodes cost nothing.

`budgets[i] = floor(budget_fractions[i] × reference_memory_units)`, where `reference_memory_units` is the memory of the given model. Budget fractions are fixed by the evaluator: HMM 0.40 / 0.30 / 0.20, PC 0.20 / 0.15 / 0.12.

## Validity (hard constraints)

A run fails if, for any instance:

- the procedure crashes, times out, or writes unreadable or malformed output;
- a CNF uses a variable outside `1..n`, or is not logically equivalent to the input. The evaluator certifies equivalence clause by clause with unit propagation plus a bounded DPLL search. An output whose equivalence cannot be certified within that search counts as non-equivalent.
- an HMM has entries outside [0, 1], or an initial distribution, emission row or transition row of a reachable state that does not sum to 1 (±1e-6), or the wrong number of symbols;
- a circuit has a malformed node, a child index that is not earlier, a leaf `p` outside [0, 1], a negative weight, sum weights that do not sum to 1 (±1e-6), a non-smooth sum, a non-decomposable product, or a root that does not cover every variable;
- any model's memory exceeds its budget.

**A failed run gets the worst value of every metric in every experiment:** 0 for all metrics.

## Metrics (all higher is better)

- `sat_implication_pruning.memory_reduction_pct`: `100 (M_in − M_out) / M_in`, clipped per instance to [0, 100] and averaged over instances.
- `hmm_flow_pruning.ll_retention_pct_mem{40,30,20}`: `100 · exp(mean over held-out task sequences of [log p_out(x) − log p_in(x)] / T)`, where `p_in` is the given model. This is per-token likelihood retention at each budget. The per-sequence change is floored at −30 nats so that zero-probability sequences stay finite. Averaged over instances.
- `pc_flow_pruning.ll_retention_pct_mem{20,15,12}`: `100 · exp(mean over held-out task samples of [log p_out(x) − log p_in(x)])`, with the per-sample change floored at −20 nats. Averaged over instances.

Retention can exceed 100 when the submitted model fits the deployment task better than the given model does.

## Slices

- **Train** (`scripts/evaluate_train.sh` → `scoring/scores_train.json`; `scripts/evaluate.sh` → `scoring/scores.json`): four public instances per kernel in `data/reason_benchmarks.json`, scored on their public held-out data (`_held_out`, which is never passed to methods).
- **Test** (`scripts/evaluate_test.sh`, no arguments → `scoring/scores_test.json`): four hidden instances per kernel from the same generating process. Your procedure is run on them with the same interface, and they are scored on hidden held-out data. Nothing is retrained by the evaluator. Every manifest in `checkpoints/` is scored.

Ranking compares each metric against the reference method, weighted by the coefficients and experiment weights in `scoring/reference.json`.

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

### Iteration 2: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

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

### [2026-06-05 00:17] - core_claim
- CPU container job `d119c227-475` completed successfully after the SAT pruning fix.
- The corrected end-to-end reproduction passed `python validate.py --compare` in the compute container with SAT, HMM, and PC scores present in `scoring/scores.json`.

</details>

### Iteration 3: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

</details>

### Iteration 4: gpt-5.5 (designer_stage_1)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

</details>

### Iteration 5: gpt-5.5 (designer_stage_2)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

</details>

### Iteration 6: gpt-5.5 (designer_stage_3)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

</details>

### Iteration 7: gpt-5.5 (packager)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 2m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

</details>

### Iteration 8: gpt-5.5 (verifier)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 7m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

### [2026-06-05 00:30] - core_claim
- Expanded `scripts/evaluate.sh` scoring output to include all benefit and constraint metrics defined in `scoring/reference.json`.
- Local full reproduction and train/test evaluator passes validate; a CPU container job is being submitted to verify the patched scoring path.

### [2026-06-05 00:45] - core_claim
- Final verification confirmed method/eval separation, method-agnostic scoring docs, reusable artifact-based evaluation, and train/test evaluator consistency.
- Fixed evaluator method-name handling and refreshed documentation; `python3 validate.py --compare` passes.

</details>

### Iteration 9: gpt-5.5 (verifier)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 12m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

### [2026-06-05 00:30] - core_claim
- Expanded `scripts/evaluate.sh` scoring output to include all benefit and constraint metrics defined in `scoring/reference.json`.
- Local full reproduction and train/test evaluator passes validate; a CPU container job is being submitted to verify the patched scoring path.

### [2026-06-05 00:45] - core_claim
- Final verification confirmed method/eval separation, method-agnostic scoring docs, reusable artifact-based evaluation, and train/test evaluator consistency.
- Fixed evaluator method-name handling and refreshed documentation; `python3 validate.py --compare` passes.

### [2026-06-05 01:15] - core_claim
- Strengthened scoring after a sub-agent audit: final regularized DAG compression is now measured against an unpruned baseline after the same two-input regularization step.
- SAT pruning artifacts now include an implication-reachability proof check for removed literals, in addition to satisfiability preservation.

</details>

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 11m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

### [2026-06-05 00:30] - core_claim
- Expanded `scripts/evaluate.sh` scoring output to include all benefit and constraint metrics defined in `scoring/reference.json`.
- Local full reproduction and train/test evaluator passes validate; a CPU container job is being submitted to verify the patched scoring path.

### [2026-06-05 00:45] - core_claim
- Final verification confirmed method/eval separation, method-agnostic scoring docs, reusable artifact-based evaluation, and train/test evaluator consistency.
- Fixed evaluator method-name handling and refreshed documentation; `python3 validate.py --compare` passes.

### [2026-06-05 01:15] - core_claim
- Strengthened scoring after a sub-agent audit: final regularized DAG compression is now measured against an unpruned baseline after the same two-input regularization step.
- SAT pruning artifacts now include an implication-reachability proof check for removed literals, in addition to satisfiability preservation.

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 1.2h | **GPU**: 0.0h
- **Jobs**: 8 total (6 completed, 2 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-04 00:00] - method_runs
- Implemented the REASON Sec. IV algorithmic pipeline for CNF/SAT, HMM, and probabilistic-circuit kernels.
- Verified that unified DAG construction, adaptive pruning, and two-input regularization execute end to end.

### [2026-06-04 00:00] - core_claim
- Reproduced the core algorithmic claim on deterministic kernel benchmarks: reasoning DAGs are reduced while preserving logical satisfiability or probabilistic likelihood.
- `scripts/reproduce.sh` writes method and baseline artifacts, `scripts/evaluate.sh` scores those artifacts without importing `method/`, and `python3 validate.py --compare` passes.

### [2026-06-05 00:00] - core_claim
- Continuation audit restored `core_claim` after re-reading `method/`, `eval/`, scripts, scoring, and briefing deliverables.
- Re-ran standalone `scripts/evaluate.sh` and full `scripts/reproduce.sh`; both regenerated scores and passed `python3 validate.py --compare`.

### [2026-06-05 00:30] - core_claim
- Expanded `scripts/evaluate.sh` scoring output to include all benefit and constraint metrics defined in `scoring/reference.json`.
- Local full reproduction and train/test evaluator passes validate; a CPU container job is being submitted to verify the patched scoring path.

### [2026-06-05 00:45] - core_claim
- Final verification confirmed method/eval separation, method-agnostic scoring docs, reusable artifact-based evaluation, and train/test evaluator consistency.
- Fixed evaluator method-name handling and refreshed documentation; `python3 validate.py --compare` passes.

### [2026-06-05 01:15] - core_claim
- Strengthened scoring after a sub-agent audit: final regularized DAG compression is now measured against an unpruned baseline after the same two-input regularization step.
- SAT pruning artifacts now include an implication-reachability proof check for removed literals, in addition to satisfiability preservation.

### [2026-11-12 18:30] - core_claim
- Hardening (iteration 11) responding to REDTEAM.md: methods are now procedures run on hidden instances; the evaluator validates returned models itself and scores them under fixed memory budgets with exact SAT equivalence. Any failure receives the worst values. See HARDENING.md.
- Audit jobs `3b7af4eb-e27` and `58503c26-32d` covered 20 cases. Every cheating shortcut fails or at best ties the reference. The genuine improvement scores +0.69, and the baseline and weaker variants rank below the reference. The held-out file leak is fixed: instances are now built in memory, and the blind answer-key scan ties the reference.

</details>


---

# Reproduction Milestones

**Current: core_claim**

## Stop Justification
- Completed at milestone `core_claim`.
