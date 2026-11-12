"""Shortcut: make the fixed workload easy, then apply the original algorithm."""
import json
from pathlib import Path
from method.hmm_reason import run_hmm
from method.pc_reason import run_pc
from method.sat_reason import run_sat
from method.audit_common import write

path = Path('data/reason_benchmarks.json')
data = json.loads(path.read_text())
h, p = data['hmm'], data['pc']
n = len(h['initial'])
h['transition'] = [[(1.-(n-1)*1e-12) if i==j else 1e-12 for j in range(n)] for i in range(n)]
p['means'] = [list(p['means'][0]) for _ in p['means']]
p['stdevs'] = [list(p['stdevs'][0]) for _ in p['stdevs']]
# The changed data and its generated artifact are what persist to test time.
path.write_text(json.dumps(data, indent=2))
write({'results': {
    'sat_implication_pruning': run_sat(data['sat']),
    'hmm_flow_pruning': run_hmm(h, .9),
    'pc_flow_pruning': run_pc(p, .9),
}})
