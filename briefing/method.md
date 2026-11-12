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
