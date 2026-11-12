#!/bin/bash
set -euo pipefail
cd /home/user
python3 - <<'PY'
import json
from pathlib import Path
Path('scoring/scores_train.json').write_text(json.dumps({'slice':'train','experiments':{}}))
PY
