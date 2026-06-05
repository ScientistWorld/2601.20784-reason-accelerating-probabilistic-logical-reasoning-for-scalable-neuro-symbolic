# Design Notes

## Checks Performed

- Read `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` side by side. The test script invokes `eval/test/evaluate.py` and writes `scoring/scores_test.json`; the train script invokes `eval/train/evaluate.py` and writes `scoring/scores_train.json`.
- Checked that both split evaluators enumerate method artifacts from disk instead of hardcoding a method name.
- Checked the evaluators for imports from `method/`; both split evaluators read JSON artifacts only.
- Grepped for train/test cross-imports. The only test-side reference to train state is the intentional `--train-scores scoring/scores_train.json` path, used only to keep the scored method set aligned.
- Checked for paper-agreement metric names in the split scoring files and `scoring/reference.json`; none were present.
- Confirmed `scoring/scores_train.json` and `scoring/scores_test.json` do not exist.
- Ran `bash -n` on both split scripts and parsed `scoring/reference.json` as JSON.

## Changes Made

- Fixed aggregate-metric trust in `eval/train/evaluate.py`: `memory_reduction_pct` is now recomputed from `baseline` and `pruned` or `reason` summaries instead of trusting a precomputed artifact field.
- Added visible `compression_balance_pct` in `eval/train/evaluate.py`, defined as the smaller of memory reduction and edge reduction. This makes train optimization less one-dimensional and catches methods that only improve one compression proxy.
- Fixed aggregate-metric trust in `eval/test/evaluate.py`: `edge_reduction_pct` and `fanin_regularized` are now recomputed from structural summaries instead of trusting precomputed artifact fields.
- Added held-out `regularized_memory_overhead_pct` in `eval/test/evaluate.py` to penalize methods that satisfy the fan-in bound by greatly expanding the regularized DAG.
- Added held-out `avg_abs_loglik_delta` for HMM and probabilistic-circuit experiments to complement retention percentage with an absolute likelihood-change constraint.
- Added explicit `"slice": "train"` and `"slice": "test"` markers to the split score outputs so copied or stale artifacts are easier to detect.
- Updated `scoring/reference.json` so every metric has `higher_is_better`, `coefficient`, and `description`.

## Runtime Concerns For Next Iteration

- The split remains a metric split over method-produced aggregate artifacts, not a fresh hidden data split. This is lightweight and method-agnostic, but it cannot detect a method that fabricates internally consistent structural summaries.
- `avg_loglik_retention_pct` may saturate at 100 when pruning improves average log-likelihood; the added `avg_abs_loglik_delta` should help expose large changes, but the next runner should confirm its scale is sensible.
- `regularized_memory_overhead_pct` penalizes graph expansion after fan-in regularization. The current reproduction may incur a positive overhead because regularization introduces binary helper nodes; the coefficient is intentionally small, but the next runner should check that it does not dominate the compression benefit.
- The split scripts were syntax-checked but not executed, per this design-only iteration's instructions.
