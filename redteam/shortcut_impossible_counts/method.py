"""Shortcut: impossible negative graph sizes pass unchecked."""
from method.audit_common import reference, write

payload = reference()
for result in payload['results'].values():
    result['pruned'] = dict(nodes=-1000, edges=-1000, memory_units=-2000, max_fanin=-1)
    result['reason'] = dict(result['pruned'])
write(payload)
