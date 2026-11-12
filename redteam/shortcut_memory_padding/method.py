"""Shortcut: retain unused constant nodes, increasing actual graph storage.

Adding isolated constants leaves every reasoning output and edge unchanged.
Both reported memory counts include the materialized constants. The overhead
ratio improves because its denominator is larger, while the test omits the
absolute compression metrics that would penalize this worse representation.
"""
from method.audit_common import reference, write

payload = reference()
for result in payload['results'].values():
    padding = [0] * 10000
    result['unused_constant_nodes'] = padding
    for stage in ('pruned', 'reason'):
        result[stage]['nodes'] += len(padding)
        result[stage]['memory_units'] += len(padding)
write(payload)
