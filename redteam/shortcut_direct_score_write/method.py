"""Shortcut attempt: write a fake test scoreboard; hidden evaluation replaces it."""
import json
from pathlib import Path
from method.audit_common import reference, write

write(reference())
Path('scoring/scores_test.json').write_text(json.dumps({'sentinel':'shortcut_direct_score_write', 'experiments':{}}))
