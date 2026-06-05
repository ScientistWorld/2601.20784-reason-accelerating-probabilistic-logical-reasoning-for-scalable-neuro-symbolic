#!/bin/bash
# Held-out test-slice evaluator.
#
# Mirrors scripts/evaluate.sh's artifact contract:
#   ./evaluate_test.sh <method_artifact> <baseline_artifact>
# With no artifact arguments, all JSON artifacts under checkpoints/ are scanned.
# When scoring/scores_train.json exists, this scores every method entry in it.

set -e

cd /home/user
export PYTHONPATH="/home/user:${PYTHONPATH:-}"
PYTHON_BIN="${PYTHON:-python3}"

mkdir -p scoring

ARGS=()
if [ $# -gt 0 ]; then
  ARGS+=(--artifact "$1")
  if [ $# -gt 1 ]; then
    ARGS+=(--artifact "$2")
  fi
else
  ARGS+=(--artifact-dir checkpoints)
fi

"$PYTHON_BIN" eval/test/evaluate.py \
  "${ARGS[@]}" \
  --train-scores scoring/scores_train.json \
  --out scoring/scores_test.json
