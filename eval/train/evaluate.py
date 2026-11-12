#!/usr/bin/env python3
"""Train-slice evaluator for the reasoning-graph compression benchmark.

Every method on disk is a manifest ``checkpoints/<anything>.json`` of the form

    {"method": "<name>", "command": ["python3", "-m", "my_package.cli"]}

For each instance the evaluator writes the method-facing instance (model +
calibration data + eval-fixed memory budgets, never the held-out data) to a
temporary file and runs ``<command> --instance IN.json --out OUT.json``.
It then scores the returned models itself (see train_kernels.py).

A run that crashes, times out, returns a malformed / invalid / non-equivalent
model or exceeds a memory budget is *failed*: it receives the worst value of
every scored metric in every experiment.

This slice scores the public instances in ``data/reason_benchmarks.json``
against their public held-out samples.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_kernels import (  # noqa: E402
    Invalid, canonical_cnf, cnf_memory, hmm_loglik, hmm_memory, hmm_validate,
    pc_loglik, pc_memory, pc_validate, score_sat,
)

ROOT = Path(__file__).resolve().parents[2]
INSTANCES = ROOT / "data" / "reason_benchmarks.json"
SLICE = "train"

EXPERIMENTS = {
    "sat_implication_pruning": "sat",
    "hmm_flow_pruning": "hmm",
    "pc_flow_pruning": "pc",
}
# Memory budgets: fraction of the original model's two-input DAG memory.
BUDGET_FRACTIONS = {"hmm": (0.40, 0.30, 0.20), "pc": (0.20, 0.15, 0.12)}
RETENTION_METRICS = {k: tuple(f"ll_retention_pct_mem{round(100 * f)}" for f in v)
                     for k, v in BUDGET_FRACTIONS.items()}
# Per-data-point log-likelihood change is floored at -CLIP nats (a zero-probability
# sequence / sample would otherwise give -inf).  HMM changes are reported per token.
CLIP = {"hmm": 30.0, "pc": 20.0}
WORST = {
    "sat_implication_pruning": {"memory_reduction_pct": 0.0},
    "hmm_flow_pruning": {m: 0.0 for m in RETENTION_METRICS["hmm"]},
    "pc_flow_pruning": {m: 0.0 for m in RETENTION_METRICS["pc"]},
}
TIMEOUT_SEC = int(os.environ.get("REASON_EVAL_TIMEOUT", "1800"))


# ----------------------------------------------------------------------------

def discover_methods(directory: Path) -> list[tuple[str, list[str], str]]:
    found = []
    names = set()
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        cmd = payload.get("command")
        if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd)):
            continue
        name = str(payload.get("method") or path.stem).strip() or path.stem
        if name in names:
            name = f"{name}@{path.stem}"
        names.add(name)
        try:
            label = str(path.resolve().relative_to(ROOT))
        except ValueError:
            label = str(path)
        found.append((name, cmd, label))
    return found


def prepare(instances: dict) -> dict:
    """Evaluator-side reference quantities for every instance."""
    prepared = {}
    for exp, kind in EXPERIMENTS.items():
        rows = []
        for inst in instances[kind]:
            if kind == "sat":
                original = canonical_cnf(inst["clauses"], inst["num_vars"])
                facing = {"task": "sat", "name": inst["name"], "num_vars": inst["num_vars"],
                          "clauses": inst["clauses"]}
                rows.append({"name": inst["name"], "instance": inst, "facing": facing,
                             "memory": cnf_memory(original)})
                continue
            if kind == "hmm":
                model = hmm_validate({k: inst[k] for k in ("initial", "transition", "emission")},
                                     inst["num_symbols"], inst["horizon"])
                m0 = hmm_memory(model, inst["horizon"])
                base_ll = hmm_loglik(model, inst["_held_out"])
                facing = {k: inst[k] for k in ("task", "name", "num_states", "num_symbols", "horizon",
                                               "initial", "transition", "emission", "calibration")}
            else:
                circ = pc_validate(inst["circuit"], inst["num_vars"])
                m0 = pc_memory(circ)
                base_ll = pc_loglik(circ, inst["_held_out"])
                facing = {k: inst[k] for k in ("task", "name", "num_vars", "circuit", "calibration")}
            budgets = [int(math.floor(f * m0)) for f in BUDGET_FRACTIONS[kind]]
            facing.update(reference_memory_units=m0, budget_fractions=list(BUDGET_FRACTIONS[kind]),
                          budgets=budgets)
            rows.append({"name": inst["name"], "instance": inst, "facing": facing, "memory": m0,
                         "budgets": budgets, "base_ll": base_ll})
        prepared[exp] = rows
    return prepared


def run_method(cmd: list[str], facing: dict, workdir: Path, log) -> dict:
    inp = workdir / "instance.json"
    out = workdir / "outputs.json"
    inp.write_text(json.dumps(facing, separators=(",", ":")), encoding="utf-8")
    if out.exists():
        out.unlink()
    argv = list(cmd)
    if argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        proc = subprocess.run(argv + ["--instance", str(inp), "--out", str(out)], cwd=str(ROOT), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise Invalid(f"method timed out after {TIMEOUT_SEC}s")
    except OSError as exc:
        raise Invalid(f"method could not be started: {exc}")
    if log is not None:
        log.write(proc.stdout.decode("utf-8", "replace")[-4000:])
    if proc.returncode != 0:
        raise Invalid(f"method exited with code {proc.returncode}")
    try:
        return json.loads(out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Invalid(f"method output unreadable: {exc}")


def score_probabilistic(kind: str, row: dict, outputs) -> dict:
    inst = row["instance"]
    if not isinstance(outputs, dict) or not isinstance(outputs.get("models"), list) \
            or len(outputs["models"]) != len(row["budgets"]):
        raise Invalid("output must contain one model per budget under 'models'")
    res = {"memory_reference": row["memory"], "budgets": row["budgets"], "memory": [], "retention": [],
           "deltas": []}
    for model, budget in zip(outputs["models"], row["budgets"]):
        if kind == "hmm":
            m = hmm_validate(model, inst["num_symbols"], inst["horizon"])
            mem = hmm_memory(m, inst["horizon"])
            if mem > budget:
                raise Invalid(f"model memory {mem} exceeds budget {budget}")
            ll = hmm_loglik(m, inst["_held_out"])
        else:
            c = pc_validate(model, inst["num_vars"])
            mem = pc_memory(c)
            if mem > budget:
                raise Invalid(f"model memory {mem} exceeds budget {budget}")
            ll = pc_loglik(c, inst["_held_out"])
        clip = CLIP[kind]
        per = float(inst["horizon"]) if kind == "hmm" else 1.0
        deltas = [max(-clip, a - b) / per for a, b in zip(ll, row["base_ll"])]
        res["memory"].append(mem)
        res["retention"].append(100.0 * math.exp(sum(deltas) / len(deltas)))
        res["deltas"].append([round(d, 6) for d in deltas])
    return res


def evaluate_method(name: str, cmd: list[str], prepared: dict, log) -> tuple[dict, dict]:
    details: dict = {}
    with tempfile.TemporaryDirectory(prefix="reason_eval_") as tmp:
        workdir = Path(tmp)
        try:
            for exp, kind in EXPERIMENTS.items():
                details[exp] = []
                for row in prepared[exp]:
                    if log is not None:
                        log.write(f"\n=== {name} / {row['name']} ===\n")
                    outputs = run_method(cmd, row["facing"], workdir, log)
                    if kind == "sat":
                        r = score_sat(row["instance"], outputs)
                    else:
                        r = score_probabilistic(kind, row, outputs)
                    r["instance"] = row["name"]
                    details[exp].append(r)
        except Invalid as exc:
            return {exp: dict(WORST[exp]) for exp in EXPERIMENTS}, {"failed": True, "reason": str(exc),
                                                                    "details": details}
        except Exception as exc:  # malformed output that slipped past type checks
            return {exp: dict(WORST[exp]) for exp in EXPERIMENTS}, {
                "failed": True, "reason": f"{type(exc).__name__}: {exc}", "details": details}
    metrics = {}
    for exp, kind in EXPERIMENTS.items():
        rows = details[exp]
        if kind == "sat":
            vals = [min(100.0, max(0.0, r["memory_reduction_pct"])) for r in rows]
            metrics[exp] = {"memory_reduction_pct": sum(vals) / len(vals)}
        else:
            metrics[exp] = {key: sum(r["retention"][b] for r in rows) / len(rows)
                            for b, key in enumerate(RETENTION_METRICS[kind])}
    return metrics, {"failed": False, "reason": "", "details": details}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods-dir", default=str(ROOT / "checkpoints"))
    parser.add_argument("--out", default=str(ROOT / "scoring" / "scores_train.json"))
    parser.add_argument("--details-out", default=None, help="optional per-instance/per-sample record")
    parser.add_argument("--log", default=None)
    parser.add_argument("--instances", default=str(INSTANCES), help=argparse.SUPPRESS)
    args = parser.parse_args()

    methods = discover_methods(Path(args.methods_dir))
    if not methods:
        raise SystemExit(f"no method manifests (with a 'command' list) in {args.methods_dir}")
    instances = json.loads(Path(args.instances).read_text(encoding="utf-8"))
    prepared = prepare(instances)
    log = open(args.log, "w", encoding="utf-8") if args.log else None

    scores = {"slice": SLICE, "experiments": {exp: {"results": {}} for exp in EXPERIMENTS}, "_status": {}}
    all_details = {}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for name, cmd, manifest in methods:
        metrics, status = evaluate_method(name, cmd, prepared, log)
        for exp in EXPERIMENTS:
            scores["experiments"][exp]["results"][name] = metrics[exp]
        scores["_status"][name] = {"manifest": manifest, "failed": status["failed"], "reason": status["reason"]}
        all_details[name] = status
        flag = "FAILED: " + status["reason"] if status["failed"] else "ok"
        print(f"[{SLICE}] {name}: {flag}", flush=True)
        for exp in EXPERIMENTS:
            print(f"    {exp}: {json.dumps(metrics[exp])}", flush=True)
        # written after every method so partial results survive an interrupted run
        out.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        if args.details_out:
            Path(args.details_out).write_text(json.dumps(all_details), encoding="utf-8")
    if log is not None:
        log.close()


if __name__ == "__main__":
    main()
