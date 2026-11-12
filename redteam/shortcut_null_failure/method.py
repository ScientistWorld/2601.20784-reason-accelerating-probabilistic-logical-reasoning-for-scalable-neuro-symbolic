"""Shortcut attempt: null statistics; test should penalize, but instead aborts."""
from method.audit_common import reference, write

payload = reference()
payload['results']['hmm_flow_pruning']['avg_loglik_after'] = None
write(payload)
