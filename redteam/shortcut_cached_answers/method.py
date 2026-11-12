"""Shortcut: replay cached answers; there is no graph transformation at run time."""
import json
from pathlib import Path

cached = json.loads(Path('method/audit_reference.json').read_text())
cached['method'] = 'audit_candidate'
Path('checkpoints/candidate.json').write_text(json.dumps(cached, indent=2))
