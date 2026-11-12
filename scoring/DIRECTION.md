# Research Direction

Stay within the paper's problem: compiling symbolic and probabilistic reasoning kernels into small executable graphs that preserve the kernel's behaviour on the deployment task.

Open directions that the benchmark can reward:

- better criteria for deciding which logical structure is redundant (more equivalence-preserving simplification of knowledge bases);
- better criteria for which probabilistic structure to remove under a tight memory budget, especially at the tightest budgets where one-shot criteria degrade;
- using the limited task calibration data well (re-parameterising what remains, iterating, merging similar structure) without overfitting it;
- compression that keeps rare-but-needed events representable.

Out of scope: replacing the reasoning kernel with an unrelated model class, using held-out or evaluator data, or exploiting the accounting instead of reducing real structure.
