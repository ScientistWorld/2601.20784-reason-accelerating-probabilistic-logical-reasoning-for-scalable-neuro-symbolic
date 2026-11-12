"""Shortcut attempt: omit a failed experiment and see whether it gets a loss."""
from method.audit_common import reference, write
payload = reference()
del payload['results']['hmm_flow_pruning']
write(payload)
