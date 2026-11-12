#!/usr/bin/env python3
"""Audit candidates (weaker variants and shortcuts) for the hardened gym.

    python3 redteam/hardened/methods/candidates.py --variant NAME --instance IN --out OUT

Each candidate behaves like a future submission: it only receives the
method-facing instance (model, calibration data, budgets) and may read the
public workspace.  Where a variant does not target a kernel it falls back to
the reference procedure for that kernel.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from method import hmm_reason as H, pc_reason as P  # noqa: E402
from method.sat_reason import run_sat  # noqa: E402

REF = {"sat": run_sat, "hmm": H.run_hmm, "pc": P.run_pc}


def _rng(inst):
    return random.Random(str(inst.get("name")) + inst["task"])


# --------------------------------------------------------------------- weaker variants

def random_pruning(inst):
    rng = _rng(inst)
    if inst["task"] == "sat":
        return {"clauses": inst["clauses"]}
    if inst["task"] == "hmm":
        pi, T, E = inst["initial"], inst["transition"], inst["emission"]
        sc = {"init": [rng.random() for _ in pi], "trans": [[rng.random() for _ in r] for r in T],
              "emit": [[rng.random() for _ in r] for r in E]}
        seq = H.removal_sequence(pi, T, E, sc)
        return {"models": [H.prune_to_budget(pi, T, E, inst["horizon"], seq, b)[0] for b in inst["budgets"]]}
    nodes, root = inst["circuit"]["nodes"], inst["circuit"]["root"]
    sc = {(i, p): rng.random() for i, n in enumerate(nodes) if n[0] == "sum" for p in range(len(n[1]))}
    seq = P.removal_sequence(nodes, root, sc)
    return {"models": [{"nodes": P.prune_to_budget(nodes, root, seq, b)[0], "root": root} for b in inst["budgets"]]}


# --------------------------------------------------------------------- shortcuts

def unpruned_claims(inst):
    """Return the unmodified model with attractive self-reported statistics."""
    fake = {"memory_reduction_pct": 99.0, "semantics_preserved": 1.0, "ll_retention_pct": 100.0}
    if inst["task"] == "sat":
        return {"clauses": inst["clauses"], **fake}
    if inst["task"] == "hmm":
        m = {k: inst[k] for k in ("initial", "transition", "emission")}
    else:
        m = dict(inst["circuit"])
    return {"models": [dict(m, **fake) for _ in inst["budgets"]], **fake}


def inflated_likelihood(inst):
    """Reference pruning, then scale probabilities up (improper model)."""
    out = REF[inst["task"]](inst)
    if inst["task"] == "hmm":
        for m in out["models"]:
            m["emission"] = [[min(1.0, 1.5 * x) for x in r] for r in m["emission"]]
    elif inst["task"] == "pc":
        for m in out["models"]:
            m["nodes"] = [n if n[0] != "sum" else ["sum", n[1], [2.0 * w for w in n[2]]] for n in m["nodes"]]
    return out


def memory_padding(inst):
    """Reference output plus unreachable padding structure."""
    out = REF[inst["task"]](inst)
    if inst["task"] == "hmm":
        for m in out["models"]:
            h, pad = len(m["initial"]), 20
            v = len(m["emission"][0])
            m["initial"] = m["initial"] + [0.0] * pad
            m["transition"] = [r + [0.0] * pad for r in m["transition"]] + \
                [[1.0 / (h + pad)] * (h + pad) for _ in range(pad)]
            m["emission"] = m["emission"] + [[1.0 / v] * v for _ in range(pad)]
    elif inst["task"] == "pc":
        for m in out["models"]:
            nodes = list(m["nodes"])
            root = m["root"]
            nodes = nodes[:root + 1] + [["leaf", 0, 0.5] for _ in range(5000)] + nodes[root + 1:]
            m["nodes"] = nodes
    return out


def tiny_model(inst):
    """Degenerate but valid model: independent marginals / single-state HMM."""
    if inst["task"] == "sat":
        return run_sat(inst)
    if inst["task"] == "hmm":
        v = inst["num_symbols"]
        counts = [1.0] * v
        for s in inst["calibration"]:
            for o in s:
                counts[o] += 1
        z = sum(counts)
        m = {"initial": [1.0], "transition": [[1.0]], "emission": [[c / z for c in counts]]}
        return {"models": [m for _ in inst["budgets"]]}
    d = inst["num_vars"]
    ones = [1.0] * d
    for x in inst["calibration"]:
        for i, b in enumerate(x):
            ones[i] += b == "1"
    n = len(inst["calibration"]) + 2
    nodes = [["leaf", i, ones[i] / n] for i in range(d)] + [["prod", list(range(d))]]
    return {"models": [{"nodes": nodes, "root": d} for _ in inst["budgets"]]}


def non_decomposable(inst):
    """Reference pruning, then multiply the root by an extra leaf over an already-covered variable."""
    out = REF[inst["task"]](inst)
    if inst["task"] == "pc":
        for m in out["models"]:
            nodes = list(m["nodes"])
            nodes.append(["leaf", 0, 0.999])
            nodes.append(["prod", [m["root"], len(nodes) - 1]])
            m["nodes"], m["root"] = nodes, len(nodes) - 1
    return out


def sat_drop_clauses(inst):
    if inst["task"] != "sat":
        return REF[inst["task"]](inst)
    out = run_sat(inst)
    rng = _rng(inst)
    return {"clauses": [c for c in out["clauses"] if rng.random() > 0.2]}


def sat_empty_clause(inst):
    if inst["task"] != "sat":
        return REF[inst["task"]](inst)
    return {"clauses": [[]]}


def crash_on_pc(inst):
    if inst["task"] == "pc":
        raise SystemExit(1)
    return REF[inst["task"]](inst)


def null_output(inst):
    if inst["task"] == "pc":
        return {"models": None}
    return REF[inst["task"]](inst)


def cached_train_answers(inst):
    """Replay reference answers computed once for the public instances."""
    pub = json.loads((ROOT / "data" / "reason_benchmarks.json").read_text())[inst["task"]]
    match = [p for p in pub if p["name"] == inst["name"]]
    src = dict(match[0] if match else pub[0])
    src.pop("_held_out", None)
    for k in ("budgets", "reference_memory_units", "budget_fractions"):
        if k in inst:
            src[k] = inst[k]
    return REF[inst["task"]](src)


def direct_score_write(inst):
    fake = {"slice": "test", "experiments": {e: {"results": {"direct_score_write": {"memory_reduction_pct": 100.0}}}
                                             for e in ("sat_implication_pruning",)}}
    (ROOT / "scoring" / "scores_test.json").write_text(json.dumps(fake))
    return REF[inst["task"]](inst)


def refit_small(inst):
    """Ignore the given model: fit a small model to the calibration data only."""
    rng = _rng(inst)
    if inst["task"] == "sat":
        return run_sat(inst)
    if inst["task"] == "pc":
        d = inst["num_vars"]
        data = [[1 if c == "1" else 0 for c in x] for x in inst["calibration"]]
        out = []
        for budget in inst["budgets"]:
            k = 2
            while 3 * (k - 1) + k * (3 * (d - 1) + d) <= budget and k < 64:
                k += 1
            k -= 1
            w = [1.0 / k] * k
            mu = [[0.25 + 0.5 * rng.random() for _ in range(d)] for _ in range(k)]
            for _it in range(25):
                cw = [1e-3] * k
                cs = [[1e-3] * d for _ in range(k)]
                for x in data:
                    lp = [math.log(w[c]) + sum(math.log(mu[c][i] if b else 1 - mu[c][i]) for i, b in enumerate(x))
                          for c in range(k)]
                    m = max(lp)
                    r = [math.exp(v - m) for v in lp]
                    z = sum(r)
                    for c in range(k):
                        cw[c] += r[c] / z
                        for i, b in enumerate(x):
                            if b:
                                cs[c][i] += r[c] / z
                tot = sum(cw)
                w = [c / tot for c in cw]
                mu = [[min(0.98, max(0.02, cs[c][i] / cw[c])) for i in range(d)] for c in range(k)]
            nodes, prods = [], []
            for c in range(k):
                ids = []
                for i in range(d):
                    nodes.append(["leaf", i, mu[c][i]])
                    ids.append(len(nodes) - 1)
                nodes.append(["prod", ids])
                prods.append(len(nodes) - 1)
            nodes.append(["sum", prods, w])
            out.append({"nodes": nodes, "root": len(nodes) - 1})
        return {"models": out}
    # hmm: Baum-Welch from random init with as many states as fit the smallest budget
    v, L = inst["num_symbols"], inst["horizon"]
    out = []
    for budget in inst["budgets"]:
        h = 2
        while H.hmm_memory([1.0 / (h + 1)] * (h + 1), [[1.0 / (h + 1)] * (h + 1)] * (h + 1),
                           [[1.0 / v] * v] * (h + 1), L) <= budget and h < 40:
            h += 1
        pi = [1.0 / h] * h
        T = [[(0.5 + rng.random()) for _ in range(h)] for _ in range(h)]
        E = [[(0.5 + rng.random()) for _ in range(v)] for _ in range(h)]
        T = [[x / sum(r) for x in r] for r in T]
        E = [[x / sum(r) for x in r] for r in E]
        for _it in range(15):
            iu, tu, eu, _ = H.forward_backward_usage(pi, T, E, inst["calibration"])
            pi = [(x + 1e-3) / (sum(iu) + 1e-3 * h) for x in iu]
            T = [[(x + 1e-3) / (sum(r) + 1e-3 * h) for x in r] for r in tu]
            E = [[(x + 1e-3) / (sum(r) + 1e-3 * v) for x in r] for r in eu]
        out.append({"initial": pi, "transition": T, "emission": E})
    return {"models": out}


def random_search(inst):
    """Brute-force flavour: sample many random feasible prunings, keep the best calibration likelihood."""
    rng = _rng(inst)
    if inst["task"] == "sat":
        return run_sat(inst)
    tries = 12
    if inst["task"] == "pc":
        nodes, root, cal = inst["circuit"]["nodes"], inst["circuit"]["root"], inst["calibration"]
        out = []
        for budget in inst["budgets"]:
            best = None
            for _ in range(tries):
                sc = {(i, p): rng.random() for i, n in enumerate(nodes) if n[0] == "sum" for p in range(len(n[1]))}
                seq = P.removal_sequence(nodes, root, sc)
                cand, _ = P.prune_to_budget(nodes, root, seq, budget)
                order = P._reachable(cand, root)
                val = P.forward(cand, order, cal)
                ll = sum(math.log(max(x, 1e-300)) for x in val[root])
                if best is None or ll > best[0]:
                    best = (ll, cand)
            out.append({"nodes": best[1], "root": root})
        return {"models": out}
    pi, T, E, L = inst["initial"], inst["transition"], inst["emission"], inst["horizon"]
    out = []
    for budget in inst["budgets"]:
        best = None
        for _ in range(tries):
            sc = {"init": [rng.random() for _ in pi], "trans": [[rng.random() for _ in r] for r in T],
                  "emit": [[rng.random() for _ in r] for r in E]}
            seq = H.removal_sequence(pi, T, E, sc)
            m, _ = H.prune_to_budget(pi, T, E, L, seq, budget)
            ll = H.forward_backward_usage(m["initial"], m["transition"], m["emission"], inst["calibration"])[3]
            if best is None or ll > best[0]:
                best = (ll, m)
        out.append(best[1])
    return {"models": out}


def read_hidden_test(inst):
    """Answer-key exploit: read held-out samples from the evaluator's files and fit to them."""
    found = None
    for path in (ROOT / "eval" / "test" / "hidden_instances.json", ROOT / "data" / "reason_benchmarks.json"):
        if path.exists():
            pool = json.loads(path.read_text()).get(inst["task"], [])
            match = [p for p in pool if p.get("name") == inst["name"]]
            if match:
                found = match[0].get("_held_out")
                break
    out = REF[inst["task"]](inst)
    if not found or inst["task"] == "sat":
        return out
    if inst["task"] == "pc":
        for m in out["models"]:
            fl = P.circuit_flows(m["nodes"], m["root"], found)
            m["nodes"] = [n if n[0] != "sum" else
                          ["sum", n[1], [(fl.get((i, p), 0.0) + 1e-3) for p in range(len(n[1]))]]
                          for i, n in enumerate(m["nodes"])]
            m["nodes"] = [n if n[0] != "sum" else ["sum", n[1], [w / sum(n[2]) for w in n[2]]] for n in m["nodes"]]
        return out
    for m in out["models"]:
        iu, tu, eu, _ = H.forward_backward_usage(m["initial"], m["transition"], m["emission"], found)
        fit = lambda c, p: [(x + 1e-6) if q > 0 else 0.0 for x, q in zip(c, p)]  # noqa: E731
        norm = lambda r: [x / sum(r) for x in r]  # noqa: E731
        m["initial"] = norm(fit(iu, m["initial"]))
        m["transition"] = [norm(fit(a, b)) for a, b in zip(tu, m["transition"])]
        m["emission"] = [norm(fit(a, b)) for a, b in zip(eu, m["emission"])]
    return out


VARIANTS = {f.__name__: f for f in (
    random_pruning, unpruned_claims, inflated_likelihood, memory_padding, tiny_model, non_decomposable,
    sat_drop_clauses, sat_empty_clause, crash_on_pc, null_output, cached_train_answers, direct_score_write,
    refit_small, random_search, read_hidden_test)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    ap.add_argument("--instance", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    inst = json.loads(Path(a.instance).read_text())
    res = VARIANTS[a.variant](inst)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")))


if __name__ == "__main__":
    main()
