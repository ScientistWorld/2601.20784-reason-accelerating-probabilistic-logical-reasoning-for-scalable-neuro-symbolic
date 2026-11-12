"""Isolate each disk-only candidate, run the actual no-argument test, restore."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path('/home/user')
os.chdir(ROOT)
name = sys.argv[1]
case = ROOT / 'redteam' / name
case.mkdir(exist_ok=True)
(ROOT/'redteam/.working').mkdir(exist_ok=True)
env = os.environ.copy()
env['PYTHONPATH'] = '/home/user'
start = time.perf_counter()
status = {'case':name, 'hidden_command':'bash scripts/evaluate_test.sh',
          'hidden_arguments':[], 'fresh_process':True}

def run(command, log):
    with (case/log).open('w') as out:
        completed = subprocess.run(command, env=env, stdout=out, stderr=subprocess.STDOUT)
    return completed.returncode

with tempfile.TemporaryDirectory(dir=ROOT/'redteam/.working') as temp:
    tmp = Path(temp)
    saved = {}
    for path in [ROOT/'data/reason_benchmarks.json', ROOT/'scoring/scores_train.json',
                 ROOT/'scoring/scores_test.json', *list((ROOT/'checkpoints').glob('*.json')),
                 *list((ROOT/'method').glob('audit_*'))]:
        if path.is_file():
            saved[path] = path.read_bytes()
    try:
        for path in (ROOT/'checkpoints').glob('*.json'):
            path.unlink()
        for path in (ROOT/'scoring/scores_train.json', ROOT/'scoring/scores_test.json'):
            path.unlink(missing_ok=True)
        shutil.copyfile(ROOT/'redteam/baseline_check/artifact.json', ROOT/'checkpoints/baseline_outputs.json')
        source_ref = ROOT/'redteam/reference_seed0/artifact.json'
        if source_ref.exists() and not name.startswith('reference_seed'):
            payload = json.loads(source_ref.read_text())
            payload['method'] = 'reason_algorithm'
            (ROOT/'checkpoints/reference_outputs.json').write_text(json.dumps(payload, indent=2))
        if name.startswith('reference_seed'):
            seed = int(name.split('seed')[-1])
            env.update(PYTHONHASHSEED=str(seed), AUDIT_SEED=str(seed))
            # Reference uses no random operations; these are independent seeded processes.
            command = [sys.executable, '-m', 'method.run_reason', '--out', 'checkpoints/candidate.json']
        elif name == 'weaker_unpruned':
            command = [sys.executable, 'baseline/run_unpruned.py', '--out', 'checkpoints/candidate.json']
        elif name.startswith('data_seed'):
            seed = name.split('seed')[-1]
            status['generate_exit'] = run([sys.executable, 'data/generate_benchmarks.py', '--seed', seed,
                                           '--out', str(case/'data.json')], 'generate.log')
            command = [sys.executable, '-m', 'method.run_reason', '--data', str(case/'data.json'),
                       '--out', 'checkpoints/candidate.json']
        else:
            shutil.copyfile(ROOT/'redteam/common.py', ROOT/'method/audit_common.py')
            shutil.copyfile(source_ref, ROOT/'method/audit_reference.json')
            candidate_module = 'audit_' + name
            shutil.copyfile(case/'method.py', ROOT/'method'/f'{candidate_module}.py')
            shutil.copyfile(ROOT/'redteam/shortcut_degenerate_empty/method.py', ROOT/'method/audit_degenerate.py')
            command = [sys.executable, '-m', 'method.'+candidate_module]
        status['method_exit'] = run(command, 'method.log')
        candidate_path = ROOT/'checkpoints/candidate.json'
        if candidate_path.exists():
            payload = json.loads(candidate_path.read_text())
            payload['method'] = 'audit_candidate'
            candidate_path.write_text(json.dumps(payload, indent=2))
            shutil.copyfile(candidate_path, case/'artifact.json')
        status['train_exit'] = run(['bash','scripts/evaluate_train.sh'], 'train.log')
        if (case/'after_train.sh').exists():
            status['after_train_exit'] = run(['bash',str(case/'after_train.sh')], 'after_train.log')
        if (ROOT/'scoring/scores_train.json').exists():
            shutil.copyfile(ROOT/'scoring/scores_train.json', case/'scores_train.json')
        status['methods_on_disk'] = [json.loads(p.read_text()).get('method',p.stem)
                                     for p in sorted((ROOT/'checkpoints').glob('*.json'))]
        status['data_sha256_at_test'] = hashlib.sha256((ROOT/'data/reason_benchmarks.json').read_bytes()).hexdigest()
        # The candidate process has exited. Only files persist into this separate
        # unmodified evaluator invocation. No argument filtering is used.
        status['test_exit'] = run(['bash','scripts/evaluate_test.sh'], 'test.log')
        status['test_score_written'] = (ROOT/'scoring/scores_test.json').exists()
        if status['test_score_written']:
            shutil.copyfile(ROOT/'scoring/scores_test.json', case/'scores_test.json')
        if name == 'shortcut_replace_fixed_data':
            shutil.copyfile(ROOT/'data/reason_benchmarks.json', case/'replaced_data.json')
    finally:
        for path in (ROOT/'checkpoints').glob('*.json'):
            path.unlink()
        for path in (ROOT/'method').glob('audit_*'):
            if path.is_file():
                path.unlink()
        for path in (ROOT/'scoring/scores_train.json', ROOT/'scoring/scores_test.json'):
            path.unlink(missing_ok=True)
        for path, content in saved.items():
            path.write_bytes(content)
        status['seconds'] = time.perf_counter()-start
        (case/'status.json').write_text(json.dumps(status, indent=2))
print(json.dumps(status), flush=True)
