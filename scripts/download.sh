#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script should be idempotent — safe to run multiple times.
# It should skip files that already exist.
#
# Update the storage estimate below as you add downloads.
#
# Estimated total download size: 0 GB
# Estimated disk usage after extraction: <1 MB
#
# This paper-specific reproduction has no remote assets. The script exists
# so a fresh clone can recreate deterministic fixtures before running jobs.

set -e

cd /home/user
export PYTHONPATH="/home/user:${PYTHONPATH:-}"
PYTHON_BIN="${PYTHON:-python3}"

# No external downloads are required. The benchmark fixtures are generated
# deterministically by data/generate_benchmarks.py.
"$PYTHON_BIN" data/generate_benchmarks.py --out data/reason_benchmarks.json
