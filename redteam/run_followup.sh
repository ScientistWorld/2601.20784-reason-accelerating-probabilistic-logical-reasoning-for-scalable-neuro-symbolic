#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
bash redteam/shortcut_memory_padding/run.sh
bash redteam/shortcut_single_gaussian/run.sh
python3 redteam/summarize.py
