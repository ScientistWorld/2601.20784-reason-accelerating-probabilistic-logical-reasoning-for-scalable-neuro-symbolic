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
