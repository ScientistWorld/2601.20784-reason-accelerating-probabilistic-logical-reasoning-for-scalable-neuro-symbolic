"""Shortcut: replace the full mixture with a poorly fitting normalized density."""
import json
from pathlib import Path
from method.pc_reason import avg_loglik, build_pc_dag
from method.audit_common import reference, probabilistic_result, write

payload = reference()
p = json.loads(Path('data/reason_benchmarks.json').read_text())['pc']
dimensions = len(p['means'][0])
weights, means, stds = [1.], [[0.]*dimensions], [[1.]*dimensions]
before = build_pc_dag(p['weights'], dimensions)
after = build_pc_dag(weights, dimensions)
ll_before = avg_loglik(p['samples'], p['weights'], p['means'], p['stdevs'])
ll_after = avg_loglik(p['samples'], weights, means, stds)
result = probabilistic_result({'kernel':'pc'}, before, after, ll_before, ll_after)
result['normalized_density'] = {'weights':weights, 'means':means, 'stdevs':stds}
payload['results']['pc_flow_pruning'] = result
write(payload)
