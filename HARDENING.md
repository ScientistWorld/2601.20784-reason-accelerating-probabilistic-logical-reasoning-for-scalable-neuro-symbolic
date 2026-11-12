# Gym hardening report (iteration 11)

This responds to the iteration-10 audit in [REDTEAM.md](REDTEAM.md). The old gym scored statistics that the method reported about itself. The redesigned gym treats a method as a **procedure**: the evaluator runs it on hidden instances, then validates and measures whatever it returns. The method still implements the paper's Sec. IV pipeline (unified DAG, implication and flow-based pruning, two-input regularization), unchanged in kind.

Evidence comes from two runs of [scripts/run.sh](scripts/run.sh). The results are in [redteam/hardened/results/](redteam/hardened/results) and [redteam/hardened/summary.json](redteam/hardened/summary.json).
- Job `3b7af4eb-e27` ran before the held-out-file fix described below.
- Job `58503c26-32d` ran after it. Every audit group in that job scored exactly its intended set of methods, and the reference's hidden scores are identical to the first job's.

## What changed, finding by finding

| REDTEAM finding | Fix | Audit case → outcome |
|---|---|---|
| Evaluator trusted self-reported counts, flags and likelihoods (fabricated, impossible or inflated-baseline outputs won) | Methods return models only. The evaluator compiles them and computes memory, equivalence and likelihood itself (`eval/test/test_kernels.py`) | `unpruned_claims` fails (budget exceeded); `inflated_likelihood` fails (improper model) |
| Memory padding improved the overhead ratio | Overhead metric removed. Memory is computed from the returned model's reachable structure only | `memory_padding` ties the reference |
| Compression could be traded for fidelity (single Gaussian, empty model) | HMM/PC have **evaluator-fixed memory budgets** (40/30/20% and 20/15/12%). Only held-out task likelihood at each budget is scored. SAT output must be **exactly equivalent**: every clause is entailed both ways, and "unknown" counts as failure | `tiny_model` −0.55, `random_pruning` −4.0; `sat_drop_clauses` and `sat_empty_clause` fail |
| Null or missing outputs crashed the evaluator with no score | Any crash, timeout, malformed, invalid or non-equivalent output gets the **worst value of every metric in every experiment** | `crash_on_pc`, `null_output`, `non_decomposable` all fail with worst values |
| Experiment registry read from editable `scores_train.json` | The test evaluator discovers manifests in `checkpoints/` and never reads `scoring/` or `data/` | `direct_score_write` ties the reference (output overwritten) |
| Public fixed data could be replaced | Hidden instances come from the hidden generator, never from `data/` | `reason_algorithm@data_replaced` gives exactly the reference score |
| Fixture too small: exact merges, 0.36 s brute force, parameter-only pruning beat flow | Larger instances (40-state HMMs, 24-variable region-graph PCs, typed CNF knowledge bases with ~400 rules). Task-shifted deployment data, so posterior flow on calibration data matters | `magnitude_pruning` (parameter-only) −0.74; `random_search` −3.4; `refit_small` −1.5 |
| Cached answers | Hidden instances are new; outputs must be equivalent or valid for *those* instances | `cached_train_answers` fails (non-equivalent CNF) |
| **New this iteration:** held-out samples were stored in plain JSON at `eval/test/hidden_instances.json`, which a running procedure could read (`read_hidden_test` +0.33 cohort, above the reference) | The file is deleted and gitignored. `eval/test/evaluate.py` rebuilds the instances **in memory** with `hidden_generator.build(HIDDEN_SEEDS)` before starting any method (checked bit-identical to the old file, about 5 s). `run.sh` scans `eval/` for leftover held-out data | Job `58503c26-32d`: `read_hidden_test` now **ties the reference exactly** (0.000), and the scan finds no held-out data under `eval/` |

## Does the score reward better research? (job `58503c26-32d`, hidden test)

Rank = Σ_e weight_e · Σ_m |coef|·dir·(x − ref)/std_m (weights SAT/HMM/PC 0.3/0.35/0.35). "Cohort" uses the std over all audited runs; "pair" uses only the reference and the candidate.

| Run | SAT mem. red. % | HMM retention @40/30/20% | PC retention @20/15/12% | Cohort rank |
|---|---:|---|---|---:|
| `better_iterative_em` (genuine improvement) | 72.45 | 98.88 / 97.47 / 91.28 | 103.52 / 102.93 / 101.89 | **+0.687** |
| `reason_algorithm` (reference) | 41.26 | 97.67 / 94.00 / 75.24 | 99.93 / 98.65 / 96.92 | 0 |
| `read_hidden_test` (blind answer-key scan) | 41.26 | 97.67 / 94.00 / 75.24 | 99.93 / 98.65 / 96.92 | 0.000 |
| `read_hidden_generator` (informed: reads the masked evaluator source) | 41.26 | 101.55 / 99.97 / 87.80 | 105.09 / 104.44 / 103.48 | +0.329 |
| `magnitude_pruning` (baseline) | 0.00 | 97.87 / 93.13 / 63.97 | 98.19 / 94.39 / 89.16 | −0.746 |
| `tiny_model` (weaker) | 41.26 | 70.40 / 70.40 / 70.40 | 94.51 / 94.51 / 94.51 | −0.541 |
| `random_pruning` (weaker) | 0.00 | 45.54 / 35.99 / 29.13 | 1.50 / 3.26 / 1.30 | −3.985 |

The full table, including every shortcut, is in [redteam/hardened/results/summary.txt](redteam/hardened/results/summary.txt).

Paired differences from the reference are far larger than test noise. Noise is estimated from per-sample paired standard errors and the instance-to-instance standard error, both in `summary.json`. For example:
- `better_iterative_em` beats the reference on HMM @20% by +16.0 points (instance s.e. 1.7, sample s.e. 0.44).
- The baseline loses to the reference on PC @12% by −7.8 points (instance s.e. 0.87).

The reference itself is deterministic, so rerunning it gives an identical score.

Headroom remains: the reference is not at any bound, and `better_iterative_em` improves every metric. The simplest cheap alternative, parameter-only pruning (the REDTEAM's "prior-only" shortcut), now loses at every tight budget.

## Residual risks (not closable inside the workspace)

- **An informed attacker who has read the masked evaluator source** can import `eval.test.hidden_generator` and rebuild the held-out samples. The `read_hidden_generator` case measures this: +0.329, still below the genuine improvement's +0.687. The gym relies on `eval/test/` staying hidden from candidates, which `scoring/CONSTRAINTS.md` also forbids reading. A blind scan of workspace files no longer finds any held-out data.
- A procedure runs with workspace write access, so it could edit `eval/` files to affect **later** evaluations. The current run is safe because the evaluator modules are imported and the instances are built before any method starts. Graders should evaluate from a clean checkout.
- The train slice's held-out samples are public in `data/reason_benchmarks.json` by design (development set). Train scores can therefore be overfitted; only the hidden test slice counts.
- This is a kernel-level, synthetic benchmark. It does not reproduce Table IV's end-to-end task accuracy, or any hardware, timing or energy claim (see `PROGRESS.md`).

## Rerun

Run `bash scripts/run.sh` as a CPU job, about 10 minutes (job `3b7af4eb-e27`: 543 s). Each audit group restores `checkpoints/` and `scoring/` afterwards. To summarize: `python3 redteam/hardened/summarize.py`.

**Restart incident.** The scheduler killed job `58503c26-32d` partway through and restarted it on another host; its log has two Hive headers.
- The killed attempt never ran its restore step, so it left three audit manifests in `checkpoints/`.
- The restarted reproduction therefore scored five methods, and the job's final `validate.py` failed with exit code 1.
- This did not affect the audit results above: each group installs and scores its own methods.

Cleanup and prevention:
- I removed the stray manifests and restored the clean score files from the job-1 commit. Local `validate.py` passes.
- `run.sh` now starts by removing all manifests and restoring public data from a backup kept inside the workspace, since `/tmp` is private to each container. It also uses `set -o pipefail`, so a failed reproduction stops the job instead of being hidden by `tee`.
