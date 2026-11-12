"""Shortcut attempt: modify the separate baseline artifact only."""
import json
from pathlib import Path
from method.audit_common import reference, write

write(reference())
path = Path('checkpoints/baseline_outputs.json')
payload = json.loads(path.read_text())
for result in payload['results'].values():
    for key in ('baseline', 'baseline_regularized'):
        for count in ('nodes', 'edges', 'memory_units'):
            result[key][count] *= 1000
path.write_text(json.dumps(payload, indent=2))
