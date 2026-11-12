#!/bin/bash
# Standard evaluation: score every registered method on the public train slice.
#
# A method is registered by a manifest  checkpoints/<anything>.json :
#   {"method": "<name>", "command": ["python3", "-m", "your.module"]}
# The evaluator runs `<command> --instance IN.json --out OUT.json` once per
# instance and recomputes every metric from the returned models.  It never
# imports method code.  Output: scoring/scores.json.
#
# Usage: bash scripts/evaluate.sh

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
mkdir -p scoring
python3 eval/train/evaluate.py --methods-dir checkpoints --out scoring/scores.json
