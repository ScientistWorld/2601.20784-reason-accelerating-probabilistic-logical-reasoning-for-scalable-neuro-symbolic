# Scoring audit

All candidates use only the public data, visible evaluator contract, baseline,
and (for improve-mode checks) original method code. No candidate imports the
hidden evaluator, reads its source, or alters Python or the evaluator process.
`run.sh` in each case installs and executes that candidate, invokes the visible
evaluator, then invokes `bash scripts/evaluate_test.sh` with **no arguments** in
a separate process. Artifacts persist on disk; no background process is used.
The hidden evaluator is unchanged. This is the same scoring boundary as a fresh
container for these pure-stdlib, file-only candidates.

Run the complete audit as a CPU job with `bash redteam/run_all.sh`.
Individual cases require `reference_seed0` and `baseline_check` first. Each case
saves its submitted artifact, train/test scores, and evaluator exit status.
`redteam/summarize.py` computes the rank with coefficient magnitudes, metric
directions, experiment weights, and population standard deviations. It reports
both a disclosed fixed audit cohort and each candidate/reference pair, because
the eventual normalization over future attempts cannot be known in advance.

`redteam/.working/` is transient backup state, never a candidate input. All
temporary changes to data, method, checkpoints, and score files are restored
even when a case fails. The original reference JSON is freshly computed from
visible method code, rather than obtained from hidden scores or old checkpoints.
