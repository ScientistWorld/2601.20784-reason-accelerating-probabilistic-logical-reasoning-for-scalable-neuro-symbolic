"""Shortcut candidate: rank prior parameters, omitting data-dependent flow."""
import json
from pathlib import Path
from method.hmm_reason import build_hmm_dag, avg_loglik as hll
from method.pc_reason import build_pc_dag, avg_loglik as pll
from method.sat_reason import run_sat
from method.audit_common import probabilistic_result, write

data = json.loads(Path('data/reason_benchmarks.json').read_text())
h, p = data['hmm'], data['pc']
n = len(h['initial'])
remove = {(i,j) for _,i,j in sorted((h['transition'][i][j],i,j) for i in range(n) for j in range(n))[:int(n*n*.3)]}
trans = []
for i, row in enumerate(h['transition']):
    new = [0. if (i,j) in remove else v for j,v in enumerate(row)]
    z = sum(new)
    trans.append([v/z for v in new])
remove_p = set(sorted(range(len(p['weights'])), key=lambda i:(p['weights'][i],i))[:int(len(p['weights'])*.3)])
weights = [0. if i in remove_p else w for i,w in enumerate(p['weights'])]
z = sum(weights)
weights = [w/z for w in weights]
write({'results': {
    'sat_implication_pruning': run_sat(data['sat']),
    'hmm_flow_pruning': probabilistic_result({'kernel':'hmm'},
        build_hmm_dag(n,len(h['sequences'][0]),h['transition']),
        build_hmm_dag(n,len(h['sequences'][0]),trans),
        hll(h['sequences'],h['initial'],h['transition'],h['emission']),
        hll(h['sequences'],h['initial'],trans,h['emission'])),
    'pc_flow_pruning': probabilistic_result({'kernel':'pc'},
        build_pc_dag(p['weights'],len(p['means'][0])), build_pc_dag(weights,len(p['means'][0])),
        pll(p['samples'],p['weights'],p['means'],p['stdevs']),
        pll(p['samples'],weights,p['means'],p['stdevs']))}})
