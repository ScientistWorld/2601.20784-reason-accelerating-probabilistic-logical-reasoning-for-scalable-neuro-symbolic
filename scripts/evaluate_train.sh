#!/bin/bash
# Train-slice evaluation (public instances, public held-out data).
# Scores every method manifest in checkpoints/ -> scoring/scores_train.json.
#
# Usage: bash scripts/evaluate_train.sh

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
mkdir -p scoring
python3 eval/train/evaluate.py --methods-dir checkpoints --out scoring/scores_train.json
