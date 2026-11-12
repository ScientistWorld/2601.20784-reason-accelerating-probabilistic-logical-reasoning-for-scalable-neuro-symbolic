#!/usr/bin/env python3
"""Generate the HIDDEN test-slice instances (same generating process as the public data, secret seeds).

Three kernel families from the paper's Sec. II-C / IV are produced, each as a
set of independent instances:

* ``sat`` -- grounded, typed knowledge bases in CNF (taxonomy implications,
  typing axioms, disjointness, multi-premise rules with type guards,
  disjunctive facts).  Every instance has a planted model, so it is
  satisfiable.
* ``hmm`` -- a "general" HMM with topic-clustered states (each state has a few
  characteristic symbols and successors), plus sequences drawn from a *task*
  distribution: the deployment task enters a subset of topics more often and
  its parameters are slightly perturbed from the general model.  ``calibration`` sequences are given to methods;
  ``validation`` sequences are held out for train-slice scoring.
* ``pc`` -- a probabilistic circuit over binary variables built on a random
  region graph (sum / product / Bernoulli-leaf nodes; latent-tree style
  mixtures in which each region state prefers a few child states), plus
  samples from a task-shifted version of the circuit (every mixture
  down-weights a random half of its branches; small parameter noise), split
  the same way.

Only Python's ``random`` module is used (Mersenne Twister, stable across
Python versions), so the output is bit-for-bit reproducible.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import hashlib

_SECRET = "reason-hidden-2601.20784-k7Qp2v"
HIDDEN_SEEDS = [int(hashlib.sha256(f"{_SECRET}/{i}".encode()).hexdigest()[:7], 16) for i in range(4)]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _dirichlet(rng: random.Random, alpha: float, n: int) -> list[float]:
    xs = [rng.gammavariate(alpha, 1.0) for _ in range(n)]
    s = sum(xs)
    if not s > 0.0:
        return [1.0 / n] * n
    return [x / s for x in xs]


def _mix(row: list[float], eta: float = 1e-3) -> list[float]:
    """Keep every entry strictly positive (dense trained-model style)."""
    n = len(row)
    s = sum(row)
    return [(1.0 - eta) * v / s + eta / n for v in row]


def _normalize(row: list[float]) -> list[float]:
    s = sum(row)
    return [v / s for v in row]


def _sample_index(rng: random.Random, probs: list[float]) -> int:
    u = rng.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if u < acc:
            return i
    return len(probs) - 1


# ----------------------------------------------------------------------------
# SAT: typed knowledge base
# ----------------------------------------------------------------------------

def make_sat(seed: int, n_types: int = 110, n_rels: int = 210, n_rules: int = 430,
             n_facts: int = 70, n_shortcuts: int = 40, n_extended: int = 40,
             n_failed: int = 8) -> dict:
    rng = random.Random(seed)
    types = list(range(1, n_types + 1))
    rels = list(range(n_types + 1, n_types + n_rels + 1))
    nvars = n_types + n_rels

    # taxonomy over types (parents always have smaller ids)
    n_roots = 8
    parents: dict[int, list[int]] = {}
    for t in types[n_roots:]:
        ps = [rng.randint(max(1, t - 25), t - 1)]
        if rng.random() < 0.12:
            q = rng.randint(1, t - 1)
            if q not in ps:
                ps.append(q)
        parents[t] = ps
    anc: dict[int, set[int]] = {t: set() for t in types}
    for t in types:
        for p in parents.get(t, []):
            anc[t] |= {p} | anc[p]
    children: dict[int, list[int]] = defaultdict(list)
    for t, ps in parents.items():
        for p in ps:
            children[p].append(t)

    # planted world (guarantees satisfiability)
    world: dict[int, bool] = {}
    for t in types:
        ps = parents.get(t, [])
        if all(world[p] for p in ps):
            world[t] = rng.random() < (0.6 if not ps else 0.5)
        else:
            world[t] = False
    rtypes: dict[int, list[int]] = {}
    rimpl: dict[int, list[int]] = {}
    for r in rels:
        k = 1 if rng.random() < 0.5 else 2
        rtypes[r] = rng.sample(types, k)
        impl = set(rtypes[r])
        for t in rtypes[r]:
            impl |= anc[t]
        rimpl[r] = sorted(impl)
        world[r] = all(world[t] for t in rtypes[r]) and rng.random() < 0.4

    clauses: list[list[int]] = []
    for t in types:
        for p in parents.get(t, []):
            clauses.append([-t, p])
    for r in rels:
        for t in rtypes[r]:
            clauses.append([-r, t])

    # sibling disjointness (only between non-related types, never both true)
    disjoint: list[tuple[int, int]] = []
    for p in types:
        ch = children.get(p, [])
        for i in range(len(ch)):
            for j in range(i + 1, len(ch)):
                a, b = ch[i], ch[j]
                if a in anc[b] or b in anc[a]:
                    continue
                if world[a] and world[b]:
                    continue
                if rng.random() < 0.35:
                    disjoint.append((a, b))
                    clauses.append([-a, -b])

    true_atoms = [a for a in range(1, nvars + 1) if world[a]]

    def rule() -> list[int] | None:
        prem_rels = rng.sample(rels, 1 if rng.random() < 0.5 else 2)
        guards: set[int] = set()
        for r in prem_rels:
            for _ in range(rng.choice([1, 2, 2, 3])):
                guards.add(rng.choice(rimpl[r]))
        if rng.random() < 0.3:
            guards.add(rng.choice(types))
        premises = list(prem_rels) + sorted(guards - set(prem_rels))
        body_true = all(world[a] for a in premises)
        pool = true_atoms if body_true else None
        for _ in range(50):
            c = rng.choice(pool) if pool else rng.randint(1, nvars)
            if c not in premises:
                return [-a for a in premises] + [c]
        return None

    rules: list[list[int]] = []
    while len(rules) < n_rules:
        r = rule()
        if r is not None:
            rules.append(r)
    clauses.extend(rules)

    # disjunctive facts, some mentioning a relation together with one of its types
    for _ in range(n_facts):
        a = rng.choice(rels)
        lits = [a]
        if rng.random() < 0.4:
            lits.append(rng.choice(rimpl[a]))
        while len(lits) < 3:
            b = rng.randint(1, nvars)
            if b not in lits:
                lits.append(b)
        if not any(world[x] for x in lits):
            lits[-1] = rng.choice([x for x in true_atoms if x not in lits])
        clauses.append(lits)

    # transitive shortcuts (entailed binary clauses)
    for _ in range(n_shortcuts):
        r = rng.choice(rels)
        deep = [t for t in rimpl[r] if t not in rtypes[r]]
        if deep:
            clauses.append([-r, rng.choice(deep)])

    # extended copies of rules (entailed by the shorter rule)
    for _ in range(n_extended):
        base = list(rng.choice(rules))
        extra = rng.randint(1, nvars)
        if extra not in [abs(x) for x in base]:
            base.insert(-1, -extra)
            clauses.append(base)

    # failed-literal gadgets: r -> a, r -> b with a, b disjoint
    false_rels = [r for r in rels if not world[r]]
    for _ in range(n_failed):
        if not disjoint or not false_rels:
            break
        a, b = rng.choice(disjoint)
        r = rng.choice(false_rels)
        clauses.append([-r, a])
        clauses.append([-r, b])

    rng.shuffle(clauses)
    for c in clauses:
        assert any((lit > 0) == world[abs(lit)] for lit in c), "planted model violated"
    return {"task": "sat", "num_vars": nvars, "clauses": clauses}


# ----------------------------------------------------------------------------
# HMM: general model + task-shifted data
# ----------------------------------------------------------------------------

def make_hmm(seed: int, states: int = 40, topics: int = 5, symbols: int = 30, horizon: int = 24,
             n_cal: int = 150, n_eval: int = 600, task_topics: int = 3, eps: float = 0.5,
             sigma: float = 0.03, stay: float = 0.85, same_alpha: float = 0.5, cross_alpha: float = 0.8,
             bg_mass: float = 0.12, bg_alpha: float = 1.0, vocab_alpha: float = 0.7,
             own_symbols: int = 4) -> dict:
    rng = random.Random(seed)
    perm = list(range(states))
    rng.shuffle(perm)
    topic = [perm[j] % topics for j in range(states)]
    vocab = {g: rng.sample(range(symbols), 8) for g in range(topics)}

    initial = _mix(_dirichlet(rng, 1.0, states))
    trans = []
    for i in range(states):
        same = [j for j in range(states) if topic[j] == topic[i]]
        other = [j for j in range(states) if topic[j] != topic[i]]
        row = [0.0] * states
        for j, w in zip(same, _dirichlet(rng, same_alpha, len(same))):
            row[j] = stay * w
        for j, w in zip(other, _dirichlet(rng, cross_alpha, len(other))):
            row[j] = (1.0 - stay) * w
        trans.append(_mix(row))
    emit = []
    for j in range(states):
        row = [bg_mass * w for w in _dirichlet(rng, bg_alpha, symbols)]
        own = rng.sample(vocab[topic[j]], own_symbols) if own_symbols < 8 else vocab[topic[j]]
        for o, w in zip(own, _dirichlet(rng, vocab_alpha, len(own))):
            row[o] += (1.0 - bg_mass) * w
        emit.append(_mix(row))

    task = set(rng.sample(range(topics), task_topics))
    tilt = [1.0 if topic[j] in task else eps for j in range(states)]
    q_init = _normalize([initial[j] * tilt[j] * math.exp(sigma * rng.gauss(0, 1)) for j in range(states)])
    q_trans = [_normalize([trans[i][j] * tilt[j] * math.exp(sigma * rng.gauss(0, 1)) for j in range(states)])
               for i in range(states)]
    q_emit = [_normalize([emit[j][o] * math.exp(sigma * rng.gauss(0, 1)) for o in range(symbols)])
              for j in range(states)]

    def sample() -> list[int]:
        z = _sample_index(rng, q_init)
        out = []
        for _ in range(horizon):
            out.append(_sample_index(rng, q_emit[z]))
            z = _sample_index(rng, q_trans[z])
        return out

    calibration = [sample() for _ in range(n_cal)]
    held_out = [sample() for _ in range(n_eval)]
    return {
        "task": "hmm",
        "num_states": states,
        "num_symbols": symbols,
        "horizon": horizon,
        "initial": initial,
        "transition": trans,
        "emission": emit,
        "calibration": calibration,
        "_held_out": held_out,
    }


# ----------------------------------------------------------------------------
# PC: region-graph circuit + task-shifted data
# ----------------------------------------------------------------------------

def make_pc(seed: int, num_vars: int = 24, k: int = 6, n_cal: int = 500, n_eval: int = 3000,
            alpha: float = 1.0, eps: float = 0.5, sigma: float = 0.05, tilt_depth: int = 99,
            leaf_beta: float = 0.25, leaf_clip: float = 0.02, fanout: int | None = None,
            latent_beta: float | None = 0.15) -> dict:
    rng = random.Random(seed)
    order = list(range(num_vars))
    rng.shuffle(order)
    nodes: list[list] = []
    depth_of: dict[int, int] = {}

    def add(node: list) -> int:
        nodes.append(node)
        return len(nodes) - 1

    def build(scope: list[int], depth: int, is_root: bool) -> list[int]:
        if len(scope) == 1:
            out = []
            for _ in range(k):
                p = min(1.0 - leaf_clip, max(leaf_clip, rng.betavariate(leaf_beta, leaf_beta)))
                out.append(add(["leaf", scope[0], p]))
            return out
        lo = max(1, len(scope) // 3)
        hi = min(len(scope) - 1, len(scope) - len(scope) // 3)
        split = rng.randint(lo, hi)
        left = build(scope[:split], depth + 1, False)
        right = build(scope[split:], depth + 1, False)
        prods = [add(["prod", [a, b]]) for a in left for b in right]
        sums = []
        for _ in range(1 if is_root else k):
            if latent_beta is not None:
                # latent-tree style: each region state picks child states independently
                pa = _dirichlet(rng, latent_beta, len(left))
                pb = _dirichlet(rng, latent_beta, len(right))
                ch = list(prods)
                w = _mix([pa[a] * pb[b] for a in range(len(left)) for b in range(len(right))])
            else:
                ch = sorted(rng.sample(prods, fanout)) if fanout and fanout < len(prods) else list(prods)
                w = _mix(_dirichlet(rng, alpha, len(ch)))
            idx = add(["sum", ch, w])
            depth_of[idx] = depth
            sums.append(idx)
        return sums

    root = build(order, 0, True)[0]

    # task distribution q: suppress half of the branches near the root, perturb the rest
    q_nodes: list[list] = []
    for idx, node in enumerate(nodes):
        if node[0] == "leaf":
            p = node[2]
            logit = math.log(p / (1.0 - p)) + sigma * rng.gauss(0, 1)
            q_nodes.append(["leaf", node[1], 1.0 / (1.0 + math.exp(-logit))])
        elif node[0] == "prod":
            q_nodes.append(node)
        else:
            w = list(node[2])
            if depth_of[idx] <= tilt_depth:
                drop = set(rng.sample(range(len(w)), len(w) // 2))
                w = [v * (eps if i in drop else 1.0) for i, v in enumerate(w)]
            w = _normalize([v * math.exp(sigma * rng.gauss(0, 1)) for v in w])
            q_nodes.append(["sum", node[1], w])

    def sample() -> str:
        x = [0] * num_vars
        stack = [root]
        while stack:
            n = q_nodes[stack.pop()]
            if n[0] == "leaf":
                x[n[1]] = 1 if rng.random() < n[2] else 0
            elif n[0] == "prod":
                stack.extend(n[1])
            else:
                stack.append(n[1][_sample_index(rng, n[2])])
        return "".join(str(b) for b in x)

    calibration = [sample() for _ in range(n_cal)]
    held_out = [sample() for _ in range(n_eval)]
    return {
        "task": "pc",
        "num_vars": num_vars,
        "circuit": {"nodes": nodes, "root": root},
        "calibration": calibration,
        "_held_out": held_out,
    }


def build(seeds: list[int]) -> dict:
    out = {"sat": [], "hmm": [], "pc": []}
    for i, s in enumerate(seeds):
        sat = make_sat(s + 1)
        sat["name"] = f"sat_h{i}"
        out["sat"].append(sat)
        hmm = make_hmm(s + 2)
        hmm["name"] = f"hmm_h{i}"
        out["hmm"].append(hmm)
        pc = make_pc(s + 3)
        pc["name"] = f"pc_h{i}"
        out["pc"].append(pc)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="eval/test/hidden_instances.json")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} exists; use --force to regenerate")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(HIDDEN_SEEDS), separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
