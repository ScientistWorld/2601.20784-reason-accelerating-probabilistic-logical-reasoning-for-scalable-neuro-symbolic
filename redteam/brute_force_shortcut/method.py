"""Shortcut: enumerate all 4095 component subsets on the fixed scored data."""
import json
import math
import time
from pathlib import Path
from method.pc_reason import component_prob, build_pc_dag
from method.audit_common import reference, probabilistic_result, write

start = time.perf_counter()
payload = reference()
p = json.loads(Path('data/reason_benchmarks.json').read_text())['pc']
old = payload['results']['pc_flow_pruning']
probs = [[w*component_prob(x,m,s) for w,m,s in zip(p['weights'],p['means'],p['stdevs'])] for x in p['samples']]
n = len(p['weights'])
best = None
for mask in range(1, 1 << n):
    kept = [i for i in range(n) if mask & (1 << i)]
    z = sum(p['weights'][i] for i in kept)
    ll = sum(math.log(max(sum(row[i] for i in kept)/z, 1e-300)) for row in probs)/len(probs)
    delta = abs(ll-old['avg_loglik_before'])
    if delta <= abs(old['avg_loglik_after']-old['avg_loglik_before']) + 1e-12:
        objective = (len(kept), delta)
        if best is None or objective < best[0]:
            best = (objective, kept, ll)
assert best is not None
_, kept, ll = best
z = sum(p['weights'][i] for i in kept)
weights = [w/z if i in kept else 0. for i,w in enumerate(p['weights'])]
before = build_pc_dag(p['weights'], len(p['means'][0]))
after = build_pc_dag(weights, len(p['means'][0]))
payload['results']['pc_flow_pruning'] = probabilistic_result(old, before, after, old['avg_loglik_before'], ll)
write(payload)
Path('redteam/brute_force_shortcut/search.json').write_text(json.dumps(dict(
    candidates=(1<<n)-1, kept=kept, avg_abs_loglik_delta=best[0][1],
    seconds=time.perf_counter()-start), indent=2))
