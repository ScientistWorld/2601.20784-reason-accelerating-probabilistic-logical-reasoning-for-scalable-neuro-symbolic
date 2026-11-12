"""Shared candidate utilities using the improve-mode public method only."""
import copy
import json
import math
from pathlib import Path


def reference():
    return json.loads(Path('method/audit_reference.json').read_text())


def write(payload, name='audit_candidate'):
    payload['method'] = name
    Path('checkpoints').mkdir(exist_ok=True)
    Path('checkpoints/candidate.json').write_text(json.dumps(payload, indent=2))


def probabilistic_result(original, before, after, ll_before, ll_after):
    return dict(kernel=original['kernel'], baseline=before.summary(),
                baseline_regularized=before.two_input_regularize().summary(),
                pruned=after.summary(), reason=after.two_input_regularize().summary(),
                avg_loglik_before=ll_before, avg_loglik_after=ll_after,
                avg_loglik_retention_pct=min(100., 100.*math.exp(ll_after-ll_before)))
