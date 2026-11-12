"""Report only metrics the no-argument hidden test actually writes."""
import json
import math
from pathlib import Path
import statistics

ROOT = Path('/home/user')
redteam = ROOT/'redteam'
config = json.loads((redteam/'scoring_reference.json').read_text())['experiments']
original = json.loads((redteam/'original_test_scores.json').read_text())

def extract(payload, method='audit_candidate'):
    return {exp: item.get('results',{}).get(method,{})
            for exp,item in payload.get('experiments',{}).items()}

stored_reference = extract(original, 'reason_algorithm')
reference = extract(json.loads((redteam/'reference_seed0/scores_test.json').read_text()))
attempts = {}
statuses = {}
for path in sorted(redteam.glob('*/status.json')):
    name = path.parent.name
    status = json.loads(path.read_text())
    statuses[name] = status
    scores = path.parent/'scores_test.json'
    if status['test_exit']==0 and scores.exists():
        attempts[name] = extract(json.loads(scores.read_text()))

def deviations(cohort):
    out = {}
    for exp, ec in config.items():
        out[exp] = {}
        for metric in ec['metrics']:
            vals = [p.get(exp,{}).get(metric) for p in cohort]
            vals = [v for v in vals if isinstance(v,(int,float)) and math.isfinite(v)]
            out[exp][metric] = statistics.pstdev(vals) if len(vals)>1 else 0.
    return out

def rank(attempt, sd):
    total = 0.
    contributions = {}
    for exp, ec in config.items():
        contributions[exp] = {}
        for metric, mc in ec['metrics'].items():
            value = attempt.get(exp,{}).get(metric)
            anchor = reference.get(exp,{}).get(metric)
            spread = sd[exp][metric]
            if value is None or anchor is None or not spread:
                continue
            direction = 1. if mc['higher_is_better'] else -1.
            c = ec['weight']*abs(mc['coefficient'])*direction*(value-anchor)/spread
            contributions[exp][metric] = c
            total += c
    return total, contributions

audit_names = [name for name in attempts if name not in ('reference_seed1','reference_seed2','data_seed20785','data_seed20786')]
cohort = [attempts[n] for n in audit_names]
sd = deviations(cohort)
quality_names = ['reference_seed0','better_exact_merge','weaker_unpruned']
quality_sd = deviations([attempts[n] for n in quality_names if n in attempts])
out = dict(normalization='population standard deviation across one candidate per named audit case; ref seed0 included, ref seeds1/2 and data-seed sensitivity excluded',
           formula='sum(weight * abs(coefficient) * direction * (candidate-reference) / std); absent values skipped',
           reference_method='audit_candidate in freshly rerun reference_seed0/scores_test.json',
           audit_cohort=audit_names, metric_std=sd, reference_metrics=reference,
           cases={}, quality_ranks={})
for name in statuses:
    status = statuses[name]
    row = {'train_exit':status['train_exit'], 'test_exit':status['test_exit'],
           'test_score_written':status['test_score_written']}
    if name in attempts:
        pair_sd = deviations([reference,attempts[name]])
        score, contributions = rank(attempts[name],sd)
        pair, pair_contributions = rank(attempts[name],pair_sd)
        row.update(audit_rank_delta=score, pair_rank_delta=pair, raw_metrics=attempts[name],
                   contributions=contributions, pair_contributions=pair_contributions)
    else:
        row['audit_rank_delta'] = None
        row['pair_rank_delta'] = None
    out['cases'][name] = row
for name in quality_names:
    if name in attempts:
        out['quality_ranks'][name] = rank(attempts[name],quality_sd)[0]
seed_names = ['reference_seed0','reference_seed1','reference_seed2']
out['seed_spread'] = {}
for exp in config:
    out['seed_spread'][exp] = {}
    for metric in reference.get(exp,{}):
        vals = [attempts[n][exp][metric] for n in seed_names if n in attempts]
        out['seed_spread'][exp][metric] = dict(min=min(vals),max=max(vals),range=max(vals)-min(vals))
seed_ranks = [rank(attempts[n],sd)[0] for n in seed_names if n in attempts]
out['seed_rank_range'] = max(seed_ranks)-min(seed_ranks)
out['stored_reference_max_abs_float_drift'] = max(
    abs(value-stored_reference[exp][metric])
    for exp, metrics in reference.items() for metric,value in metrics.items())
out['missing_configured_metrics'] = {
    exp:[m for m,mc in ec['metrics'].items() if mc['coefficient'] and m not in reference.get(exp,{})]
    for exp,ec in config.items()}
(redteam/'summary.json').write_text(json.dumps(out,indent=2))
for name,row in out['cases'].items():
    print(name, 'test_exit=',row['test_exit'], 'rank=',row['audit_rank_delta'], 'pair=',row['pair_rank_delta'])
print('quality ranks',out['quality_ranks'])
print('seed rank spread',out['seed_rank_range'])
