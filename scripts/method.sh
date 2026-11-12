#!/bin/bash
# Register the paper's method (REASON Sec. IV: unified DAG, adaptive pruning,
# two-input regularisation) and score it on the public train slice.
#
# A method is a procedure: the evaluators call
#   python3 -m method.reason_cli --instance IN.json --out OUT.json
# once per instance.  Registration = a manifest in checkpoints/.
#
# Usage: bash scripts/method.sh

set -e
cd "$(dirname "$0")/.."
mkdir -p checkpoints
cat > checkpoints/reason_algorithm.json <<'JSON'
{"method": "reason_algorithm", "command": ["python3", "-m", "method.reason_cli"]}
JSON
bash scripts/download.sh
if [ "${SKIP_EVAL:-0}" != "1" ]; then
  bash scripts/evaluate.sh
fi
