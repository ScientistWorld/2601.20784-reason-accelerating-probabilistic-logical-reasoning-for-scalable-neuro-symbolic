#!/usr/bin/env python3
"""Run a group of candidates through the real hidden test (and optionally train).

    python3 redteam/hardened/harness.py GROUP name1 name2 ... [--train]

Each name is a manifest spec from SPECS.  The current checkpoints/*.json are
backed up, replaced by the group's manifests, `bash scripts/evaluate_test.sh`
is run with no arguments (REASON_DETAILS_OUT only adds a per-sample record),
results are copied to redteam/hardened/results/GROUP_*, and the original
manifests and score files are restored.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "redteam" / "hardened" / "results"
CAND = ["python3", "redteam/hardened/methods/candidates.py", "--variant"]
SPECS = {
    "reason_algorithm": ["python3", "-m", "method.reason_cli"],
    "magnitude_pruning": ["python3", "-m", "baseline.magnitude_cli"],
    "better_iterative_em": ["python3", "redteam/hardened/methods/better_iterative_em.py"],
}


def command(name):
    return SPECS.get(name) or CAND + [name]


def main():
    group, names = sys.argv[1], [a for a in sys.argv[2:] if not a.startswith("--")]
    do_train = "--train" in sys.argv
    RES.mkdir(parents=True, exist_ok=True)
    ck = ROOT / "checkpoints"
    backup = {p: p.read_bytes() for p in ck.glob("*.json")}
    scores = {p: p.read_bytes() for p in (ROOT / "scoring").glob("scores*.json")}
    status = {"group": group, "methods": names, "hidden_command": "bash scripts/evaluate_test.sh", "arguments": []}
    try:
        for p in ck.glob("*.json"):
            p.unlink()
        for n in names:
            (ck / f"{n}.json").write_text(json.dumps({"method": n, "command": command(n)}))
        env = dict(os.environ, REASON_DETAILS_OUT=str(RES / f"{group}_test_details.json"))
        t = time.time()
        with open(RES / f"{group}_test.log", "w") as log:
            status["test_exit"] = subprocess.run(["bash", "scripts/evaluate_test.sh"], cwd=ROOT, env=env,
                                                 stdout=log, stderr=subprocess.STDOUT).returncode
        status["test_seconds"] = round(time.time() - t, 1)
        if (ROOT / "scoring/scores_test.json").exists():
            shutil.copyfile(ROOT / "scoring/scores_test.json", RES / f"{group}_scores_test.json")
        if do_train:
            t = time.time()
            with open(RES / f"{group}_train.log", "w") as log:
                status["train_exit"] = subprocess.run(["bash", "scripts/evaluate_train.sh"], cwd=ROOT,
                                                      stdout=log, stderr=subprocess.STDOUT).returncode
            status["train_seconds"] = round(time.time() - t, 1)
            if (ROOT / "scoring/scores_train.json").exists():
                shutil.copyfile(ROOT / "scoring/scores_train.json", RES / f"{group}_scores_train.json")
    finally:
        for p in ck.glob("*.json"):
            p.unlink()
        for p, b in backup.items():
            p.write_bytes(b)
        for p in (ROOT / "scoring").glob("scores*.json"):
            if p not in scores:
                p.unlink()
        for p, b in scores.items():
            p.write_bytes(b)
        (RES / f"{group}_status.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status))


if __name__ == "__main__":
    main()
