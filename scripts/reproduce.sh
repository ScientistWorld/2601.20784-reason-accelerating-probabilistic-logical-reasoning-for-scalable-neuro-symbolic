#!/bin/bash
# Reproduce the gym's reference results end to end (CPU only, ~1 h):
#   data -> register baseline + REASON -> train slice -> hidden test slice.

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

bash scripts/download.sh
SKIP_EVAL=1 bash scripts/baseline.sh
SKIP_EVAL=1 bash scripts/method.sh
bash scripts/evaluate_train.sh
cp scoring/scores_train.json scoring/scores.json
bash scripts/evaluate_test.sh
python3 validate.py
