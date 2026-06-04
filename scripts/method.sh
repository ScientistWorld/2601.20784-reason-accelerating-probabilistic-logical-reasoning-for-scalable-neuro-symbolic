#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user
export PYTHONPATH="/home/user:${PYTHONPATH:-}"
PYTHON_BIN="${PYTHON:-python3}"

"$PYTHON_BIN" data/generate_benchmarks.py --out data/reason_benchmarks.json
"$PYTHON_BIN" -m method.run_reason --data data/reason_benchmarks.json --out checkpoints/reason_outputs.json

if [ ! -f checkpoints/baseline_outputs.json ]; then
  bash scripts/baseline.sh
fi

bash scripts/evaluate.sh checkpoints/reason_outputs.json checkpoints/baseline_outputs.json
