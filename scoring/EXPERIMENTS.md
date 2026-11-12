# Experiments

All three experiments ask the same question for a different family of reasoning kernels: how small can the executable reasoning graph become while what it computes for the deployment task is preserved?  Each method is run as a procedure on hidden instances it has never seen; the evaluator compiles and measures whatever the procedure returns.

`sat_implication_pruning` — logical knowledge bases in CNF.  Establishes how much graph memory can be removed without changing the formula's meaning at all: the output must have exactly the same models as the input (certified by the evaluator), and the score is the memory reduction.  Exactness is a hard gate, so compression can only come from genuinely redundant structure.

`hmm_flow_pruning` — a general-domain hidden Markov model deployed on a narrower task.  Establishes how much task likelihood can be kept when the model must fit into 40%, 30% and 20% of its original graph memory.  The budgets are fixed by the evaluator, so a method cannot trade fidelity for compression; the loosest budget tests the "comparable accuracy at large memory savings" regime, the tightest budgets test where simple criteria break down.

`pc_flow_pruning` — a general probabilistic circuit deployed on a narrower task.  Same question at 20%, 15% and 12% of the original memory: held-out task likelihood of a valid circuit that fits each budget.

Across experiments, the unchanged model (or any model over budget, improper, or non-equivalent) does not count as a solution: the run is failed and receives the worst value everywhere.
