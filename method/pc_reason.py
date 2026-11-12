"""REASON probabilistic-circuit pruning via circuit flow (Sec. IV-B b).

For an input x the flow through sum edge (n, c) is

    F_{n,c}(x) = theta_{n,c} p_c(x) / p_n(x) * F_n(x),

with F_root(x) = 1 and a product node passing its flow to every child.  The
cumulative flow over the task dataset D (calibration samples) is
F_{n,c}(D) = sum_x F_{n,c}(x).  Edges with the smallest cumulative flow are
pruned (globally, across all sum nodes) until the compiled two-input DAG fits
the memory budget; every sum node keeps at least one input and its weights
are renormalised.
"""

from __future__ import annotations

from method.reason_dag import build_pc_dag


def _reachable(nodes, root):
    seen = set()
    stack = [root]
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        if nodes[i][0] != "leaf":
            stack.extend(nodes[i][1])
    return sorted(seen)


def forward(nodes, order, samples):
    cols = {}
    val = {}
    for i in order:
        node = nodes[i]
        if node[0] == "leaf":
            v = node[1]
            if v not in cols:
                cols[v] = [1 if x[v] == "1" else 0 for x in samples]
            p, q = node[2], 1.0 - node[2]
            val[i] = [p if b else q for b in cols[v]]
        elif node[0] == "prod":
            ch = node[1]
            acc = val[ch[0]]
            for c in ch[1:]:
                acc = [a * b for a, b in zip(acc, val[c])]
            val[i] = acc
        else:
            acc = [0.0] * len(samples)
            for c, w in zip(node[1], node[2]):
                if w > 0.0:
                    acc = [a + w * b for a, b in zip(acc, val[c])]
            val[i] = acc
    return val


def circuit_flows(nodes, root, samples):
    """Cumulative edge flow {(sum_node, child_position): F_{n,c}(D)}."""
    order = _reachable(nodes, root)
    val = forward(nodes, order, samples)
    n = len(samples)
    flow = {root: [1.0] * n}
    edge_flow = {}
    for i in reversed(order):
        f = flow.pop(i, None)
        if f is None or nodes[i][0] == "leaf":
            continue
        node = nodes[i]
        if node[0] == "prod":
            for c in node[1]:
                cur = flow.get(c)
                flow[c] = list(f) if cur is None else [x + y for x, y in zip(cur, f)]
            continue
        pn = val[i]
        ratio = [fx / px if px > 0.0 else 0.0 for fx, px in zip(f, pn)]
        for pos, (c, w) in enumerate(zip(node[1], node[2])):
            if w <= 0.0:
                continue
            fc = [w * pc * r for pc, r in zip(val[c], ratio)]
            edge_flow[(i, pos)] = sum(fc)
            cur = flow.get(c)
            flow[c] = fc if cur is None else [x + y for x, y in zip(cur, fc)]
    return edge_flow


def pc_memory(nodes, root, removed=frozenset()) -> int:
    return build_pc_dag(nodes, root, removed).regularized_memory()


def removal_sequence(nodes, root, scores):
    order = _reachable(nodes, root)
    left = {}
    cands = []
    for i in order:
        node = nodes[i]
        if node[0] != "sum":
            continue
        left[i] = sum(1 for w in node[2] if w > 0.0)
        for pos, w in enumerate(node[2]):
            if w > 0.0:
                cands.append((scores.get((i, pos), 0.0), (i, pos)))
    cands.sort()
    seq = []
    for _s, (i, pos) in cands:
        if left[i] <= 1:
            continue
        left[i] -= 1
        seq.append((i, pos))
    return seq


def apply_removal(nodes, removed):
    out = []
    for i, node in enumerate(nodes):
        if node[0] != "sum":
            out.append(node)
            continue
        kept = [(c, w) for p, (c, w) in enumerate(zip(node[1], node[2])) if w > 0.0 and (i, p) not in removed]
        z = sum(w for _, w in kept)
        out.append(["sum", [c for c, _ in kept], [w / z for _, w in kept]])
    return out


def prune_to_budget(nodes, root, seq, budget):
    def mem(k):
        return pc_memory(nodes, root, frozenset(seq[:k]))

    lo, hi = 0, len(seq)
    if mem(0) <= budget:
        hi = 0
    while lo < hi:
        mid = (lo + hi) // 2
        if mem(mid) <= budget:
            hi = mid
        else:
            lo = mid + 1
    return apply_removal(nodes, set(seq[:hi])), hi


def run_pc(instance: dict) -> dict:
    nodes = instance["circuit"]["nodes"]
    root = instance["circuit"]["root"]
    scores = circuit_flows(nodes, root, instance["calibration"])
    seq = removal_sequence(nodes, root, scores)
    models = []
    for budget in instance["budgets"]:
        pruned, _k = prune_to_budget(nodes, root, seq, budget)
        models.append({"nodes": pruned, "root": root})
    return {"models": models}
