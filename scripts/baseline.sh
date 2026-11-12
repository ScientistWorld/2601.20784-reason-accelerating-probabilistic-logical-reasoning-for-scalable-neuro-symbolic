#!/bin/bash
# Register the data-free magnitude-pruning baseline (baseline/magnitude_cli.py):
# smallest-parameter entries are removed until each memory budget is met;
# logical formulas are returned unchanged.
#
# Usage: bash scripts/baseline.sh

set -e
cd "$(dirname "$0")/.."
mkdir -p checkpoints
cat > checkpoints/magnitude_pruning.json <<'JSON'
{"method": "magnitude_pruning", "command": ["python3", "-m", "baseline.magnitude_cli"]}
JSON
bash scripts/download.sh
if [ "${SKIP_EVAL:-0}" != "1" ]; then
  bash scripts/evaluate.sh
fi
