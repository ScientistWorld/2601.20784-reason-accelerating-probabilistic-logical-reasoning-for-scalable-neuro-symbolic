#!/bin/bash
# Job: reproduce the reference end to end, then run the hardening audit
# (variants and shortcuts through the real no-argument hidden test).
# CPU only.  Each stage saves its outputs before the next starts.

set -eo pipefail
cd /home/user
export PYTHONPATH="/home/user:${PYTHONPATH:-}"
mkdir -p redteam/hardened/results redteam/hardened/work
DATA_BACKUP=redteam/hardened/work/reason_benchmarks.backup.json

# 0. Self-heal.  The scheduler may kill and restart this job (job 58503c26-32d
#    did); a killed audit step cannot run its restore, so undo anything an
#    earlier attempt may have left: corrupted public data, audit manifests.
if [ -f "$DATA_BACKUP" ]; then
  echo "restoring public data left corrupted by an interrupted attempt"
  cp "$DATA_BACKUP" data/reason_benchmarks.json && rm -f "$DATA_BACKUP"
fi
rm -f checkpoints/*.json   # reproduce.sh re-registers the two official manifests

# 1. Reference reproduction (official scores: reference + baseline only)
bash scripts/reproduce.sh 2>&1 | tee redteam/hardened/results/reproduce.log

# 2. Hardening audit (every group restores checkpoints/ and scoring/ afterwards)
H="python3 redteam/hardened/harness.py"
$H quality reason_algorithm magnitude_pruning better_iterative_em random_pruning tiny_model --train
$H shortcuts unpruned_claims inflated_likelihood memory_padding non_decomposable sat_drop_clauses \
   sat_empty_clause crash_on_pc null_output cached_train_answers direct_score_write
$H slow refit_small random_search read_hidden_test read_hidden_generator

# 2b. No file under eval/ may hold held-out samples (they are generated in memory)
python3 - <<'PY' | tee redteam/hardened/results/heldout_scan.txt
import json, pathlib
hits = []
for p in sorted(pathlib.Path("eval").rglob("*")):
    if p.is_file() and p.suffix not in (".py", ".pyc") and b"_held_out" in p.read_bytes():
        hits.append(str(p))
print("non-code files under eval/ containing held-out samples:", hits or "none")
PY

# 3. Hidden test does not read data/: corrupt the public data file, rerun the reference
cp data/reason_benchmarks.json "$DATA_BACKUP"   # in the workspace, so a restart can restore it
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
cp "$DATA_BACKUP" data/reason_benchmarks.json && rm -f "$DATA_BACKUP"

python3 redteam/hardened/summarize.py | tee redteam/hardened/results/summary.txt
ls checkpoints | tee redteam/hardened/results/final_checkpoints.txt   # must be the two official manifests
python3 validate.py
