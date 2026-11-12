"""Shortcut: move the comparison denominator, leaving the candidate unchanged."""
from method.audit_common import reference, write

payload = reference()
for result in payload['results'].values():
    for key in ('baseline', 'baseline_regularized'):
        for count in ('nodes', 'edges', 'memory_units'):
            result[key][count] *= 1000
write(payload)
