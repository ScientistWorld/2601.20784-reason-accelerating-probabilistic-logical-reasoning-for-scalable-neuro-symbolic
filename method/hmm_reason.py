"""REASON HMM pruning via posterior flow (Sec. IV-B b).

Expected transition and emission usage is computed with the forward-backward
algorithm on the task's calibration sequences (posterior state and
transition probabilities).  Transitions, emissions and initial-state entries
with the smallest expected usage are pruned until the compiled, two-input
regularised DAG fits the memory budget; each row is renormalised and keeps
at least one entry.
"""

from __future__ import annotations

import math
from operator import mul

from method.reason_dag import build_hmm_dag


def forward_backward_usage(initial, trans, emit, seqs):
    """Expected initial / transition / emission counts summed over ``seqs``."""
    h = len(initial)
    v = len(emit[0])
    n = len(seqs)
    length = len(seqs[0])
    obs = [[s[t] for s in seqs] for t in range(length)]
    edges = [(i, j, w) for i, row in enumerate(trans) for j, w in enumerate(row) if w > 0.0]

    alphas = []
    scales = []
    dead = [False] * n
    a = [[initial[j] * emit[j][o] for o in obs[0]] for j in range(h)]
    for t in range(length):
        if t > 0:
            new = [[0.0] * n for _ in range(h)]
            prev = alphas[-1]
            for i, j, w in edges:
                new[j] = [x + w * y for x, y in zip(new[j], prev[i])]
            a = [[x * emit[j][o] for x, o in zip(new[j], obs[t])] for j in range(h)]
        c = [sum(col) for col in zip(*a)]
        for s_idx, x in enumerate(c):
            if not x > 0.0:
                dead[s_idx] = True  # zero probability under this model: excluded from usage
        inv = [0.0 if dead[s_idx] else 1.0 / x for s_idx, x in enumerate(c)]
        a = [[x * y for x, y in zip(row, inv)] for row in a]
        alphas.append(a)
        scales.append(c)

    live = [s_idx for s_idx in range(n) if not dead[s_idx]]
    loglik = (sum(sum(math.log(scales[t][s_idx]) for t in range(length)) for s_idx in live) / n
              if len(live) == n else -math.inf)
    init_u = [0.0] * h
    trans_u = [[0.0] * h for _ in range(h)]
    emit_u = [[0.0] * v for _ in range(h)]
    beta = [[1.0] * n for _ in range(h)]
    for t in range(length - 1, -1, -1):
        gamma = [[x * y for x, y in zip(alphas[t][j], beta[j])] for j in range(h)]
        for j in range(h):
            row = emit_u[j]
            for g, o in zip(gamma[j], obs[t]):
                row[o] += g
        if t == 0:
            init_u = [sum(g) for g in gamma]
            break
        inv_c = [0.0 if dead[s_idx] else 1.0 / x for s_idx, x in enumerate(scales[t])]
        u = [[e * b * ic for e, b, ic in zip((emit[j][o] for o in obs[t]), beta[j], inv_c)] for j in range(h)]
        prev_alpha = alphas[t - 1]
        new_beta = [[0.0] * n for _ in range(h)]
        for i, j, w in edges:
            new_beta[i] = [x + w * y for x, y in zip(new_beta[i], u[j])]
            trans_u[i][j] += w * sum(map(mul, prev_alpha[i], u[j]))
        beta = new_beta
    return init_u, trans_u, emit_u, loglik


def _apply(initial, trans, emit, removed):
    pi = [0.0 if ("init", j) in removed else w for j, w in enumerate(initial)]
    t = [[0.0 if ("trans", i, j) in removed else w for j, w in enumerate(row)] for i, row in enumerate(trans)]
    e = [[0.0 if ("emit", j, o) in removed else w for o, w in enumerate(row)] for j, row in enumerate(emit)]
    return pi, t, e


def _renormalize(row):
    s = sum(row)
    return [x / s for x in row] if s > 0.0 else row


def hmm_memory(initial, trans, emit, horizon: int) -> int:
    return build_hmm_dag(initial, trans, emit, horizon).regularized_memory()


def removal_sequence(initial, trans, emit, scores):
    """Candidates in increasing score order, skipping removals that would empty a row."""
    cands = []
    for j, w in enumerate(initial):
        if w > 0.0:
            cands.append((scores["init"][j], ("init", j)))
    for i, row in enumerate(trans):
        for j, w in enumerate(row):
            if w > 0.0:
                cands.append((scores["trans"][i][j], ("trans", i, j)))
    for j, row in enumerate(emit):
        for o, w in enumerate(row):
            if w > 0.0:
                cands.append((scores["emit"][j][o], ("emit", j, o)))
    cands.sort(key=lambda x: (x[0], x[1]))
    left_init = sum(1 for w in initial if w > 0.0)
    left_trans = [sum(1 for w in row if w > 0.0) for row in trans]
    left_emit = [sum(1 for w in row if w > 0.0) for row in emit]
    seq = []
    for _score, key in cands:
        if key[0] == "init":
            if left_init <= 1:
                continue
            left_init -= 1
        elif key[0] == "trans":
            if left_trans[key[1]] <= 1:
                continue
            left_trans[key[1]] -= 1
        else:
            if left_emit[key[1]] <= 1:
                continue
            left_emit[key[1]] -= 1
        seq.append(key)
    return seq


def prune_to_budget(initial, trans, emit, horizon: int, seq, budget: int):
    """Smallest prefix of ``seq`` whose removal fits ``budget`` (memory is monotone)."""
    def mem(k):
        return hmm_memory(*_apply(initial, trans, emit, set(seq[:k])), horizon)

    lo, hi = 0, len(seq)
    if mem(0) <= budget:
        hi = 0
    while lo < hi:
        mid = (lo + hi) // 2
        if mem(mid) <= budget:
            hi = mid
        else:
            lo = mid + 1
    pi, t, e = _apply(initial, trans, emit, set(seq[:hi]))
    return {"initial": _renormalize(pi),
            "transition": [_renormalize(r) for r in t],
            "emission": [_renormalize(r) for r in e]}, hi


def run_hmm(instance: dict) -> dict:
    initial, trans, emit = instance["initial"], instance["transition"], instance["emission"]
    init_u, trans_u, emit_u, _ll = forward_backward_usage(initial, trans, emit, instance["calibration"])
    seq = removal_sequence(initial, trans, emit, {"init": init_u, "trans": trans_u, "emit": emit_u})
    models = []
    for budget in instance["budgets"]:
        model, _k = prune_to_budget(initial, trans, emit, instance["horizon"], seq, budget)
        models.append(model)
    return {"models": models}
