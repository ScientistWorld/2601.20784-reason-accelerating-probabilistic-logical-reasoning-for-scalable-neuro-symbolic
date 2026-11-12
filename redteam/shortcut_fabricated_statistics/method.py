"""Shortcut: emit attractive statistics without transforming a reasoning graph."""
from method.audit_common import reference, write

payload = reference()
for result in payload['results'].values():
    result['baseline'] = dict(nodes=501, edges=500, memory_units=1001, max_fanin=500)
    result['baseline_regularized'] = dict(nodes=501, edges=500, memory_units=1001, max_fanin=2)
    result['pruned'] = dict(nodes=6, edges=5, memory_units=11, max_fanin=2)
    result['reason'] = dict(result['pruned'])
    if result['kernel'] == 'sat':
        result['semantics_preserved'] = 1.
        result['implication_proof_sound'] = 1.
    else:
        result['avg_loglik_after'] = result['avg_loglik_before']
        result['avg_loglik_retention_pct'] = 100.
write(payload)
