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
