"""Genuine improvement: exact HMM lumping and exact Gaussian coalescing.

Groups are discovered from model parameters, without fixture-specific indices.
Both transformations preserve the distribution for all observations. Original
SAT pruning and the original two-input regularization are retained.
"""
import json
import math
from pathlib import Path
from method.hmm_reason import build_hmm_dag, avg_loglik as hll, _forward_backward
from method.pc_reason import build_pc_dag, avg_loglik as pll, component_prob
from method.sat_reason import run_sat
from method.audit_common import probabilistic_result, write


def groups_by(keys):
    groups = {}
    for i, key in enumerate(keys):
        groups.setdefault(key, []).append(i)
    return list(groups.values())


data = json.loads(Path('data/reason_benchmarks.json').read_text())
h, p = data['hmm'], data['pc']
# Refine the emission partition until it is strongly lumpable.
groups = groups_by([tuple(row) for row in h['emission']])
while True:
    signatures = []
    for i, emit in enumerate(h['emission']):
        signatures.append((tuple(emit), tuple(round(sum(h['transition'][i][j] for j in g), 13) for g in groups)))
    refined = groups_by(signatures)
    if refined == groups:
        break
    groups = refined
trans = [[sum(h['transition'][g[0]][j] for j in dest) for dest in groups] for g in groups]
max_lump_error = max(abs(sum(h['transition'][i][j] for j in dest)-trans[k][l])
                     for k, g in enumerate(groups) for i in g for l, dest in enumerate(groups))
assert max_lump_error < 1e-12
initial = [sum(h['initial'][i] for i in g) for g in groups]
emit = [h['emission'][g[0]] for g in groups]
before_h = build_hmm_dag(len(h['initial']), len(h['sequences'][0]), h['transition'])
after_h = build_hmm_dag(len(initial), len(h['sequences'][0]), trans)
h_before = hll(h['sequences'], h['initial'], h['transition'], h['emission'])
h_after = hll(h['sequences'], initial, trans, emit)
max_sequence_delta = max(abs(_forward_backward(s, h['initial'], h['transition'], h['emission'])[0]
                             - _forward_backward(s, initial, trans, emit)[0]) for s in h['sequences'])
assert max_sequence_delta < 1e-10

pc_groups = groups_by([(tuple(m), tuple(s)) for m, s in zip(p['means'], p['stdevs'])])
weights = [sum(p['weights'][k] for k in g) for g in pc_groups]
means = [p['means'][g[0]] for g in pc_groups]
stds = [p['stdevs'][g[0]] for g in pc_groups]
before_p = build_pc_dag(p['weights'], len(p['means'][0]))
after_p = build_pc_dag(weights, len(means[0]))
p_before = pll(p['samples'], p['weights'], p['means'], p['stdevs'])
p_after = pll(p['samples'], weights, means, stds)
max_pc_delta = max(abs(sum(w*component_prob(x,m,s) for w,m,s in zip(p['weights'],p['means'],p['stdevs']))
                       - sum(w*component_prob(x,m,s) for w,m,s in zip(weights,means,stds))) for x in p['samples'])
assert max_pc_delta < 1e-12
write({'results': {
    'sat_implication_pruning': run_sat(data['sat']),
    'hmm_flow_pruning': probabilistic_result({'kernel':'hmm'}, before_h, after_h, h_before, h_after),
    'pc_flow_pruning': probabilistic_result({'kernel':'pc'}, before_p, after_p, p_before, p_after),
}})
Path('redteam/better_exact_merge/validation.json').write_text(json.dumps(dict(
    hmm_states_before=len(h['initial']), hmm_states_after=len(initial),
    pc_components_before=len(p['weights']), pc_components_after=len(weights),
    max_lump_error=max_lump_error, max_sequence_loglik_delta=max_sequence_delta,
    max_sample_density_delta=max_pc_delta), indent=2))
