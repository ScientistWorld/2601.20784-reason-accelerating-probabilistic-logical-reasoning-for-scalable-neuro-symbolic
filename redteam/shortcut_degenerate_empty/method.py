"""Shortcut: an empty reasoning model, with truthfully failed fidelity flags."""
import math
from pathlib import Path
from method.audit_common import reference, write

def likelihood(_input):
    return 0.

payload = reference()
for result in payload['results'].values():
    result['pruned'] = dict(nodes=1, edges=0, memory_units=1, max_fanin=0)
    result['reason'] = dict(result['pruned'])
    if result['kernel'] == 'sat':
        result['semantics_preserved'] = 0.
        result['implication_proof_sound'] = 0.
    else:
        result['avg_loglik_after'] = math.log(1e-300)
        result['avg_loglik_retention_pct'] = 0.
write(payload)
Path('method/audit_model.json').write_text('{"output": "empty", "probability": 0}')
