#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
mkdir -p redteam/baseline_check
python3 baseline/run_unpruned.py --out redteam/baseline_check/artifact.json
for name in reference_seed0 reference_seed1 reference_seed2 weaker_unpruned better_exact_merge \
  data_seed20785 data_seed20786 shortcut_prior_only brute_force_shortcut \
  shortcut_fabricated_statistics shortcut_inflated_baseline shortcut_cached_answers \
  shortcut_degenerate_empty shortcut_impossible_counts shortcut_replace_fixed_data \
  shortcut_registry_omission shortcut_null_failure shortcut_direct_score_write \
  shortcut_baseline_artifact_only shortcut_missing_experiment \
  shortcut_memory_padding shortcut_single_gaussian; do
  bash "redteam/$name/run.sh"
done
python3 redteam/summarize.py
