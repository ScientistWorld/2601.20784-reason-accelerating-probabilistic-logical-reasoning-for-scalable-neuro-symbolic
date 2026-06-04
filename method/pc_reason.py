"""REASON probabilistic-circuit DAG lowering and circuit-flow pruning."""

from __future__ import annotations

import math

from method.reason_dag import DAG


def gaussian_pdf(x: float, mean: float, stdev: float) -> float:
    var = stdev * stdev
    return math.exp(-0.5 * (x - mean) ** 2 / var) / math.sqrt(2.0 * math.pi * var)


def component_prob(x: list[float], mean: list[float], stdev: list[float]) -> float:
    p = 1.0
    for xi, mi, si in zip(x, mean, stdev):
        p *= gaussian_pdf(xi, mi, si)
    return p


def build_pc_dag(weights: list[float], dimensions: int) -> DAG:
    dag = DAG()
    component_nodes = []
    for k, w in enumerate(weights):
        if w <= 0.0:
            continue
        leaves = [dag.add(f"leaf_{k}_{d}", "gaussian_leaf") for d in range(dimensions)]
        prod = dag.add(f"component_{k}", "product", leaves, w)
        component_nodes.append(prod)
    dag.add("root", "sum", component_nodes)
    return dag


def avg_loglik(samples: list[list[float]], weights: list[float], means: list[list[float]], stdevs: list[list[float]]) -> float:
    total = 0.0
    for x in samples:
        p = sum(w * component_prob(x, m, s) for w, m, s in zip(weights, means, stdevs))
        total += math.log(max(p, 1e-300))
    return total / len(samples)


def run_pc(instance: dict, prune_fraction: float = 0.30) -> dict:
    weights = instance["weights"]
    means = instance["means"]
    stdevs = instance["stdevs"]
    samples = instance["samples"]
    flow = [0.0 for _ in weights]
    for x in samples:
        contrib = [w * component_prob(x, m, s) for w, m, s in zip(weights, means, stdevs)]
        denom = sum(contrib)
        for k, c in enumerate(contrib):
            flow[k] += c / max(denom, 1e-300)
    remove_n = max(1, int(len(weights) * prune_fraction))
    remove = {k for _v, k in sorted((v, k) for k, v in enumerate(flow))[:remove_n]}
    kept_weights = [0.0 if k in remove else w for k, w in enumerate(weights)]
    z = sum(kept_weights)
    kept_weights = [w / z for w in kept_weights]
    before = build_pc_dag(weights, len(means[0]))
    after_prune = build_pc_dag(kept_weights, len(means[0]))
    after = after_prune.two_input_regularize()
    ll_before = avg_loglik(samples, weights, means, stdevs)
    ll_after = avg_loglik(samples, kept_weights, means, stdevs)
    return {
        "kernel": "pc",
        "baseline": before.summary(),
        "pruned": after_prune.summary(),
        "reason": after.summary(),
        "sum_edges_before": len(weights),
        "sum_edges_after": len(weights) - len(remove),
        "avg_loglik_before": ll_before,
        "avg_loglik_after": ll_after,
        "avg_loglik_retention_pct": min(100.0, 100.0 * math.exp(ll_after - ll_before)),
    }
