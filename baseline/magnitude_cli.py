#!/usr/bin/env python3
"""Magnitude-pruning baseline (data-free; self-contained, does not use method/).

    python3 -m baseline.magnitude_cli --instance IN.json --out OUT.json

* sat: returns the formula unchanged (no logical simplification).
* hmm / pc: removes the entries / sum edges with the smallest *parameter
  value* (transition, emission and initial probabilities; mixture weights)
  until the two-input DAG fits each memory budget, keeping at least one entry
  per row / sum node and renormalising.  The calibration data are ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def reg_cost(k: int) -> int:
    return 1 if k <= 0 else (2 if k == 1 else 3 * (k - 1))


# ----------------------------------------------------------------------------- HMM

def hmm_memory(pi, trans, emit, horizon: int) -> int:
    succ = [[j for j, v in enumerate(r) if v > 0.0] for r in trans]
    e_nnz = [sum(1 for v in r if v > 0.0) for r in emit]
    e_sym = [{o for o, v in enumerate(r) if v > 0.0} for r in emit]
    cur = {j for j, v in enumerate(pi) if v > 0.0}
    total = 0
    prev: set = set()
    for t in range(horizon):
        if t == 0:
            total += 2 * len(cur)
        else:
            fan: dict = {}
            for i in prev:
                for j in succ[i]:
                    fan[j] = fan.get(j, 0) + 1
            cur = set(fan)
            total += sum(reg_cost(f) + 3 for f in fan.values())
        syms: set = set()
        for j in cur:
            total += reg_cost(e_nnz[j])
            syms |= e_sym[j]
        total += len(syms)
        prev = cur
    return total + reg_cost(len(prev))


def hmm_magnitude(inst: dict) -> dict:
    pi, T, E, L = inst["initial"], inst["transition"], inst["emission"], inst["horizon"]
    cands = [(w, ("i", j)) for j, w in enumerate(pi) if w > 0.0]
    cands += [(w, ("t", i, j)) for i, r in enumerate(T) for j, w in enumerate(r) if w > 0.0]
    cands += [(w, ("e", j, o)) for j, r in enumerate(E) for o, w in enumerate(r) if w > 0.0]
    cands.sort()
    left = {("i",): sum(1 for w in pi if w > 0.0)}
    for i, r in enumerate(T):
        left[("t", i)] = sum(1 for w in r if w > 0.0)
    for j, r in enumerate(E):
        left[("e", j)] = sum(1 for w in r if w > 0.0)
    seq = []
    for _w, key in cands:
        row = key[:1] if key[0] == "i" else key[:2]
        if left[row] <= 1:
            continue
        left[row] -= 1
        seq.append(key)

    def build(k):
        rm = set(seq[:k])
        p = [0.0 if ("i", j) in rm else w for j, w in enumerate(pi)]
        t = [[0.0 if ("t", i, j) in rm else w for j, w in enumerate(r)] for i, r in enumerate(T)]
        e = [[0.0 if ("e", j, o) in rm else w for o, w in enumerate(r)] for j, r in enumerate(E)]
        return p, t, e

    models = []
    for budget in inst["budgets"]:
        lo, hi = 0, len(seq)
        if hmm_memory(*build(0), L) <= budget:
            hi = 0
        while lo < hi:
            mid = (lo + hi) // 2
            if hmm_memory(*build(mid), L) <= budget:
                hi = mid
            else:
                lo = mid + 1
        p, t, e = build(hi)
        norm = lambda r: [x / sum(r) for x in r]  # noqa: E731
        models.append({"initial": norm(p), "transition": [norm(r) for r in t], "emission": [norm(r) for r in e]})
    return {"models": models}


# ----------------------------------------------------------------------------- PC

def pc_memory(nodes, root, removed) -> int:
    reach = set()
    stack = [root]
    while stack:
        i = stack.pop()
        if i in reach:
            continue
        reach.add(i)
        n = nodes[i]
        if n[0] == "prod":
            stack.extend(n[1])
        elif n[0] == "sum":
            stack.extend(c for p, (c, w) in enumerate(zip(n[1], n[2])) if w > 0.0 and (i, p) not in removed)
    rep, canon = {}, {}
    for i in sorted(reach):
        n = nodes[i]
        if n[0] == "leaf":
            rep[i], canon[i] = i, []
        else:
            if n[0] == "prod":
                ch = [rep[c] for c in n[1]]
            else:
                ch = [rep[c] for p, (c, w) in enumerate(zip(n[1], n[2])) if w > 0.0 and (i, p) not in removed]
            if len(ch) == 1:
                rep[i] = ch[0]
            else:
                rep[i], canon[i] = i, ch
    keep = set()
    stack = [rep[root]]
    while stack:
        i = stack.pop()
        if i not in keep:
            keep.add(i)
            stack.extend(canon[i])
    return sum(reg_cost(len(canon[i])) for i in keep)


def pc_magnitude(inst: dict) -> dict:
    nodes, root = inst["circuit"]["nodes"], inst["circuit"]["root"]
    cands = sorted((w, (i, p)) for i, n in enumerate(nodes) if n[0] == "sum" for p, w in enumerate(n[2]) if w > 0.0)
    left = {i: sum(1 for w in n[2] if w > 0.0) for i, n in enumerate(nodes) if n[0] == "sum"}
    seq = []
    for _w, (i, p) in cands:
        if left[i] <= 1:
            continue
        left[i] -= 1
        seq.append((i, p))
    models = []
    for budget in inst["budgets"]:
        lo, hi = 0, len(seq)
        if pc_memory(nodes, root, frozenset()) <= budget:
            hi = 0
        while lo < hi:
            mid = (lo + hi) // 2
            if pc_memory(nodes, root, frozenset(seq[:mid])) <= budget:
                hi = mid
            else:
                lo = mid + 1
        rm = set(seq[:hi])
        out = []
        for i, n in enumerate(nodes):
            if n[0] != "sum":
                out.append(n)
                continue
            kept = [(c, w) for p, (c, w) in enumerate(zip(n[1], n[2])) if w > 0.0 and (i, p) not in rm]
            z = sum(w for _, w in kept)
            out.append(["sum", [c for c, _ in kept], [w / z for _, w in kept]])
        models.append({"nodes": out, "root": root})
    return {"models": models}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    inst = json.loads(Path(args.instance).read_text(encoding="utf-8"))
    if inst["task"] == "sat":
        res = {"clauses": inst["clauses"]}
    elif inst["task"] == "hmm":
        res = hmm_magnitude(inst)
    else:
        res = pc_magnitude(inst)
    Path(args.out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
