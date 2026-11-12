#!/usr/bin/env python3
"""Genuinely better variant (audit only): iterative flow pruning + regularised EM re-estimation.

PC/HMM: prune toward the budget in several rounds, recomputing flows on the
already-pruned model each round; then one EM (Baum-Welch / circuit-flow)
M-step on the calibration data with a Dirichlet prior centred on the current
parameters.  SAT: the reference literal pruning followed by removal of clauses
that unit propagation shows to be entailed by the rest (sequential, so the
formula stays equivalent).
"""
import argparse, json, sys
from pathlib import Path
from method import hmm_reason as H, pc_reason as P
from method.sat_reason import prune_redundant_literals

ROUNDS = 4
PRIOR = 10.0


def _bcp_conflict(clauses, occ, assume):
    val = {}
    queue = []
    def put(l):
        v = abs(l)
        if v in val:
            return val[v] == (l > 0)
        val[v] = l > 0; queue.append(l); return True
    for l in assume:
        if not put(l):
            return True
    for c in clauses:
        if c is not None and len(c) == 1 and not put(c[0]):
            return True
    while queue:
        l = queue.pop()
        for ci in occ.get(-l, ()):
            c = clauses[ci]
            if c is None:
                continue
            un = None; n = 0; sat = False
            for x in c:
                if abs(x) in val:
                    if val[abs(x)] == (x > 0):
                        sat = True; break
                else:
                    n += 1; un = x
            if sat or n > 1:
                continue
            if n == 0 or not put(un):
                return True
    return False


def better_sat(inst):
    clauses, _ = prune_redundant_literals([list(c) for c in inst["clauses"]])
    clauses = [tuple(sorted(set(c))) for c in clauses]
    clauses = list(dict.fromkeys(clauses))
    occ = {}
    for i, c in enumerate(clauses):
        for l in c:
            occ.setdefault(l, []).append(i)
    order = sorted(range(len(clauses)), key=lambda i: -len(clauses[i]))
    live = list(clauses)
    for i in order:
        c = live[i]
        live[i] = None
        if not _bcp_conflict(live, occ, [-l for l in c]):
            live[i] = c
    return {"clauses": [list(c) for c in live if c is not None]}


def better_pc(inst):
    nodes, root, cal = inst["circuit"]["nodes"], inst["circuit"]["root"], inst["calibration"]
    m0 = inst["reference_memory_units"]
    models = []
    for budget in inst["budgets"]:
        cur = [list(n) for n in nodes]
        mem = P.pc_memory(cur, root)
        for r in range(1, ROUNDS + 1):
            target = int(m0 * (budget / m0) ** (r / ROUNDS)) if r < ROUNDS else budget
            target = max(target, budget)
            if mem <= target:
                continue
            fl = P.circuit_flows(cur, root, cal)
            seq = P.removal_sequence(cur, root, fl)
            cur, _ = P.prune_to_budget(cur, root, seq, target)
            mem = P.pc_memory(cur, root)
        fl = P.circuit_flows(cur, root, cal)
        out = []
        for i, n in enumerate(cur):
            if n[0] != "sum":
                out.append(n); continue
            w = [fl.get((i, p), 0.0) + PRIOR * x for p, x in enumerate(n[2])]
            z = sum(w)
            out.append(["sum", n[1], [x / z for x in w]])
        models.append({"nodes": out, "root": root})
    return {"models": models}


def better_hmm(inst):
    pi0, t0, e0, cal, L = inst["initial"], inst["transition"], inst["emission"], inst["calibration"], inst["horizon"]
    m0 = inst["reference_memory_units"]
    models = []
    for budget in inst["budgets"]:
        pi, T, E = pi0, t0, e0
        mem = H.hmm_memory(pi, T, E, L)
        for r in range(1, ROUNDS + 1):
            target = int(m0 * (budget / m0) ** (r / ROUNDS)) if r < ROUNDS else budget
            target = max(target, budget)
            if mem <= target:
                continue
            iu, tu, eu, _ = H.forward_backward_usage(pi, T, E, cal)
            seq = H.removal_sequence(pi, T, E, {"init": iu, "trans": tu, "emit": eu})
            m, _ = H.prune_to_budget(pi, T, E, L, seq, target)
            pi, T, E = m["initial"], m["transition"], m["emission"]
            mem = H.hmm_memory(pi, T, E, L)
        iu, tu, eu, _ = H.forward_backward_usage(pi, T, E, cal)
        def est(cnt, prior):
            w = [c + PRIOR * p if p > 0.0 else 0.0 for c, p in zip(cnt, prior)]
            z = sum(w)
            return [x / z for x in w]
        models.append({"initial": est(iu, pi), "transition": [est(a, b) for a, b in zip(tu, T)],
                       "emission": [est(a, b) for a, b in zip(eu, E)]})
    return {"models": models}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--instance"); ap.add_argument("--out")
    a = ap.parse_args()
    inst = json.loads(Path(a.instance).read_text())
    res = {"sat": better_sat, "hmm": better_hmm, "pc": better_pc}[inst["task"]](inst)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")))


if __name__ == "__main__":
    main()
