#!/bin/bash
# Prepare all data needed by this environment (idempotent).
#
# Estimated total download size: 0 GB (no external assets)
# Estimated disk usage: ~3 MB
#
# This benchmark has no external datasets or model weights: every instance is
# produced deterministically by agent-authored code (Python's `random`
# module, stable across versions).  The public train-slice instances live in
# data/reason_benchmarks.json (tracked in git); this script regenerates the
# file only when it is missing.  Hidden test instances are produced by the
# evaluator's own code under eval/test/ and are not part of this script.

set -e
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON:-python3}"

if [ ! -f data/reason_benchmarks.json ]; then
  "$PYTHON_BIN" data/generate_benchmarks.py --out data/reason_benchmarks.json
else
  echo "data/reason_benchmarks.json present"
fi
