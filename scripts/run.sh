#!/bin/bash
# Job: reproduce the reference end to end, then run the hardening audit
# (variants and shortcuts through the real no-argument hidden test).
# CPU only.  Each stage saves its outputs before the next starts.

set -e
cd /home/user
export PYTHONPATH="/home/user:${PYTHONPATH:-}"
mkdir -p redteam/hardened/results

# 1. Reference reproduction (official scores: reference + baseline only)
bash scripts/reproduce.sh 2>&1 | tee redteam/hardened/results/reproduce.log

# 2. Hardening audit (every group restores checkpoints/ and scoring/ afterwards)
H="python3 redteam/hardened/harness.py"
$H quality reason_algorithm magnitude_pruning better_iterative_em random_pruning tiny_model --train
$H shortcuts unpruned_claims inflated_likelihood memory_padding non_decomposable sat_drop_clauses \
   sat_empty_clause crash_on_pc null_output cached_train_answers direct_score_write
$H slow refit_small random_search read_hidden_test

# 3. Hidden test does not read data/: corrupt the public data file, rerun the reference
cp data/reason_benchmarks.json /tmp/reason_benchmarks.backup.json
python3 - <<'PY'
import json
p = "data/reason_benchmarks.json"
d = json.load(open(p))
for inst in d["hmm"]:
    h = len(inst["initial"])
    inst["transition"] = [[1.0 / h] * h for _ in range(h)]
for inst in d["pc"]:
    inst["circuit"]["nodes"] = [n if n[0] != "sum" else ["sum", n[1], [1.0 / len(n[1])] * len(n[1])]
                                for n in inst["circuit"]["nodes"]]
json.dump(d, open(p, "w"))
PY
set +e
$H data_replaced reason_algorithm
set -e
cp /tmp/reason_benchmarks.backup.json data/reason_benchmarks.json

python3 redteam/hardened/summarize.py | tee redteam/hardened/results/summary.txt
python3 validate.py
