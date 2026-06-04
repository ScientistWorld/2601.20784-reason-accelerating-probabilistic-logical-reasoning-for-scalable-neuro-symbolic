"""REASON HMM DAG lowering and posterior-flow pruning."""

from __future__ import annotations

import math

from method.reason_dag import DAG


def build_hmm_dag(states: int, steps: int, transition: list[list[float]]) -> DAG:
    dag = DAG()
    prev = [dag.add(f"z_0_{s}", "state") for s in range(states)]
    for t in range(1, steps):
        cur = []
        for j in range(states):
            parents = [prev[i] for i in range(states) if transition[i][j] > 0.0]
            cur.append(dag.add(f"z_{t}_{j}", "sum_product", parents))
        prev = cur
    dag.add("likelihood", "sum", prev)
    return dag


def _forward_backward(seq: list[int], initial: list[float], trans: list[list[float]], emit: list[list[float]]) -> tuple[float, list[list[list[float]]]]:
    n = len(initial)
    alpha = []
    scale = []
    first = [initial[s] * emit[s][seq[0]] for s in range(n)]
    z = sum(first)
    alpha.append([v / z for v in first])
    scale.append(z)
    for obs in seq[1:]:
        row = [sum(alpha[-1][i] * trans[i][j] for i in range(n)) * emit[j][obs] for j in range(n)]
        z = sum(row)
        alpha.append([v / z for v in row])
        scale.append(z)
    beta = [[1.0] * n for _ in seq]
    for t in range(len(seq) - 2, -1, -1):
        row = [sum(trans[i][j] * emit[j][seq[t + 1]] * beta[t + 1][j] for j in range(n)) / scale[t + 1] for i in range(n)]
        beta[t] = row
    xis = []
    for t in range(len(seq) - 1):
        denom = 0.0
        mat = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                val = alpha[t][i] * trans[i][j] * emit[j][seq[t + 1]] * beta[t + 1][j]
                mat[i][j] = val
                denom += val
        xis.append([[v / max(denom, 1e-300) for v in row] for row in mat])
    return sum(math.log(max(s, 1e-300)) for s in scale), xis


def avg_loglik(sequences: list[list[int]], initial: list[float], trans: list[list[float]], emit: list[list[float]]) -> float:
    return sum(_forward_backward(seq, initial, trans, emit)[0] for seq in sequences) / len(sequences)


def run_hmm(instance: dict, prune_fraction: float = 0.30) -> dict:
    trans = instance["transition"]
    emit = instance["emission"]
    initial = instance["initial"]
    sequences = instance["sequences"]
    states = len(initial)
    usage = [[0.0] * states for _ in range(states)]
    for seq in sequences:
        _ll, xis = _forward_backward(seq, initial, trans, emit)
        for mat in xis:
            for i in range(states):
                for j in range(states):
                    usage[i][j] += mat[i][j]
    candidates = sorted((usage[i][j], i, j) for i in range(states) for j in range(states) if trans[i][j] > 0.0)
    remove_n = max(1, int(len(candidates) * prune_fraction))
    remove = {(i, j) for _u, i, j in candidates[:remove_n]}
    pruned = []
    for i, row in enumerate(trans):
        new = [0.0 if (i, j) in remove else row[j] for j in range(states)]
        total = sum(new)
        pruned.append([v / total if total else row[j] for j, v in enumerate(new)])
    before = build_hmm_dag(states, len(sequences[0]), trans)
    after_prune = build_hmm_dag(states, len(sequences[0]), pruned)
    after = after_prune.two_input_regularize()
    ll_before = avg_loglik(sequences, initial, trans, emit)
    ll_after = avg_loglik(sequences, initial, pruned, emit)
    return {
        "kernel": "hmm",
        "baseline": before.summary(),
        "pruned": after_prune.summary(),
        "reason": after.summary(),
        "transition_edges_before": states * states,
        "transition_edges_after": states * states - len(remove),
        "avg_loglik_before": ll_before,
        "avg_loglik_after": ll_after,
        "avg_loglik_retention_pct": min(100.0, 100.0 * math.exp(ll_after - ll_before)),
    }
