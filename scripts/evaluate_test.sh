#!/bin/bash
# Hidden test-slice evaluation.  Takes no arguments and scores every method
# manifest in checkpoints/ on hidden instances held only under eval/test/,
# writing scoring/scores_test.json.  Each registered procedure is run once
# per hidden instance (it sees the model, calibration data and budgets, never
# the held-out data); nothing is retrained.
#
# Usage: bash scripts/evaluate_test.sh

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
mkdir -p scoring
EXTRA=()
if [ -n "${REASON_DETAILS_OUT:-}" ]; then
  EXTRA+=(--details-out "$REASON_DETAILS_OUT")
fi
python3 eval/test/evaluate.py --methods-dir checkpoints --out scoring/scores_test.json "${EXTRA[@]}"
