# Evaluation

## Metrics

`memory_reduction_pct` measures the percentage reduction in graph memory units, where a memory unit is one stored node or one stored edge in the compiled reasoning graph. Higher is better.

`edge_reduction_pct` measures the percentage reduction in stored graph edges. Higher is better.

`compression_balance_pct` is the smaller of `memory_reduction_pct` and `edge_reduction_pct`, rewarding methods that reduce both storage dimensions rather than improving only one.

`final_regularized_memory_reduction_pct` measures memory reduction after both the candidate graph and the uncompressed reference graph are expressed through the same bounded-local-interface format. Higher is better.

`final_regularized_edge_reduction_pct` measures edge reduction under that same final bounded-local-interface format. Higher is better.

`fanin_regularized` is 1 when the final graph satisfies the benchmark's local-interface bound and 0 otherwise. Higher is better.

`regularized_memory_overhead_pct` measures extra memory introduced by the final bounded-local-interface representation relative to the reduced graph. Lower is better.

`semantics_preserved` is used for logical workloads and is 1 when the transformed formula preserves satisfiability semantics. Higher is better.

`implication_proof_sound` is used for logical workloads and is 1 when every removed logical element has a valid artifact-level justification under the benchmark dependency rules. Higher is better.

`avg_loglik_retention_pct` is used for probabilistic workloads and is `100 * exp(avg_loglik_after - avg_loglik_before)` over the fixed evaluation sequences or samples. Higher is better, with 100 meaning no likelihood loss.

`avg_abs_loglik_delta` is used for probabilistic workloads and measures the absolute change in average log-likelihood after transformation. Lower is better.

## Baselines and Targets

The baseline is the uncompressed graph representation of each workload. The target is a transformed graph that reduces memory while retaining logical or probabilistic behavior. Paper-reported algorithm optimization targets from Table IV are used as references: 21% memory reduction with unchanged 81% accuracy for AlphaGeometry/MiniF2F-style logical reasoning, 29% memory reduction with 86/87 success-rate retention for Ctrl-G/CoAuthor-style HMM reasoning, and 37% memory reduction with 0.752/0.758 AUPRC retention for R2-Guard/TwinSafety-style probabilistic reasoning.

## Evaluation Protocol

Run `scripts/reproduce.sh` or run `scripts/baseline.sh`, `scripts/method.sh`, and `scripts/evaluate.sh` in sequence. A candidate method must write a JSON artifact with a top-level `method` name and per-experiment `results` entries containing graph summaries and fidelity fields. Evaluation reads that artifact plus `checkpoints/baseline_outputs.json` and writes `scoring/scores.json`. Evaluation code must not import the candidate method.
