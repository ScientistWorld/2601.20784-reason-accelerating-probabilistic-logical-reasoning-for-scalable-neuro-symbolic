#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
python3 redteam/harness.py reference_seed1
