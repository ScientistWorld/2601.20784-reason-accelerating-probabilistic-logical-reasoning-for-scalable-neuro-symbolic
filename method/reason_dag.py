"""REASON Stage 1 (unified DAG representation) and Stage 3 (two-input regularisation).

All three kernels are compiled into the same DAG abstraction (Sec. IV-A,
Fig. 5): nodes are atomic reasoning operations, edges are dependencies.

* CNF  : literal leaves -> clause OR nodes -> formula AND node.
* HMM  : unrolled over time; per step and live state an emission sum over
         observation indicators, a sum over predecessor states (transition
         factors) and a product combining both; a root sums the last step.
* PC   : the circuit's own sum / product / leaf nodes (after dropping zero
         weights and single-input identity nodes).

Stage 3 (Sec. IV-C) decomposes every node with more than two inputs into a
balanced binary tree of two-input nodes.  Memory is counted as nodes + edges
of that final DAG.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    op: str
    inputs: list = field(default_factory=list)


class DAG:
    def __init__(self) -> None:
        self.nodes: dict = {}

    def add(self, name, op: str, inputs=None):
        self.nodes[name] = Node(op, list(inputs or []))
        return name

    def edge_count(self) -> int:
        return sum(len(n.inputs) for n in self.nodes.values())

    def memory_units(self) -> int:
        return len(self.nodes) + self.edge_count()

    def max_fanin(self) -> int:
        return max((len(n.inputs) for n in self.nodes.values()), default=0)

    def two_input_regularize(self) -> "DAG":
        """Balanced binary-tree decomposition of every node with fan-in > 2."""
        out = DAG()
        counter = 0
        for name, node in self.nodes.items():
            level = list(node.inputs)
            while len(level) > 2:
                nxt = []
                for k in range(0, len(level) - 1, 2):
                    mid = ("reg", counter)
                    counter += 1
                    out.add(mid, node.op, level[k:k + 2])
                    nxt.append(mid)
                if len(level) % 2:
                    nxt.append(level[-1])
                level = nxt
            out.add(name, node.op, level)
        return out

    def regularized_memory(self) -> int:
        """Memory of ``two_input_regularize()`` without materialising it."""
        return sum(reg_cost(len(n.inputs)) for n in self.nodes.values())


def reg_cost(fanin: int) -> int:
    if fanin <= 0:
        return 1
    if fanin == 1:
        return 2
    return 3 * (fanin - 1)


# ---------------------------------------------------------------------------
# Stage 1 builders
# ---------------------------------------------------------------------------

def build_cnf_dag(clauses) -> DAG:
    dag = DAG()
    names = []
    for idx, clause in enumerate(clauses):
        lits = []
        for lit in clause:
            key = ("lit", lit)
            if key not in dag.nodes:
                dag.add(key, "literal")
            lits.append(key)
        names.append(dag.add(("clause", idx), "or", lits))
    dag.add("formula", "and", names)
    return dag


def build_hmm_dag(initial, transition, emission, horizon: int) -> DAG:
    dag = DAG()
    succ = [[j for j, v in enumerate(row) if v > 0.0] for row in transition]
    e_sym = [[o for o, v in enumerate(row) if v > 0.0] for row in emission]
    cur = sorted(j for j, v in enumerate(initial) if v > 0.0)
    prev: list = []
    for t in range(horizon):
        if t > 0:
            preds: dict = {}
            for i in prev:
                for j in succ[i]:
                    preds.setdefault(j, []).append(i)
            cur = sorted(preds)
        used = sorted({o for j in cur for o in e_sym[j]})
        for o in used:
            dag.add(("x", t, o), "indicator")
        for j in cur:
            em = dag.add(("em", t, j), "sum", [("x", t, o) for o in e_sym[j]])
            if t == 0:
                dag.add(("a", t, j), "product", [em])
            else:
                s = dag.add(("s", t, j), "sum", [("a", t - 1, i) for i in preds[j]])
                dag.add(("a", t, j), "product", [s, em])
        prev = cur
    dag.add("root", "sum", [("a", horizon - 1, j) for j in prev])
    return dag


def canonical_pc(nodes, root, removed=frozenset()):
    """Drop zero-weight / removed edges, collapse single-input nodes, keep reachable.

    ``removed`` holds (sum_node, child_position) pairs.  Returns
    (order, canonical_nodes, top) with canonical_nodes[i] = (kind, children, weights).
    """
    rep: dict = {}
    canon: dict = {}
    stack = [root]
    reach = set()
    while stack:
        i = stack.pop()
        if i in reach:
            continue
        reach.add(i)
        node = nodes[i]
        if node[0] == "sum":
            stack.extend(c for p, (c, w) in enumerate(zip(node[1], node[2])) if w > 0.0 and (i, p) not in removed)
        elif node[0] == "prod":
            stack.extend(node[1])
    for i in sorted(reach):
        node = nodes[i]
        if node[0] == "leaf":
            rep[i] = i
            canon[i] = ("leaf", (), ())
        elif node[0] == "prod":
            ch = [rep[c] for c in node[1]]
            if len(ch) == 1:
                rep[i] = ch[0]
            else:
                rep[i] = i
                canon[i] = ("prod", ch, ())
        else:
            pairs = [(rep[c], w) for p, (c, w) in enumerate(zip(node[1], node[2]))
                     if w > 0.0 and (i, p) not in removed]
            if len(pairs) == 1:
                rep[i] = pairs[0][0]
            else:
                rep[i] = i
                canon[i] = ("sum", [c for c, _ in pairs], [w for _, w in pairs])
    top = rep[root]
    keep = set()
    stack = [top]
    while stack:
        i = stack.pop()
        if i in keep:
            continue
        keep.add(i)
        stack.extend(canon[i][1])
    order = sorted(keep)
    return order, {i: canon[i] for i in order}, top


def build_pc_dag(nodes, root, removed=frozenset()) -> DAG:
    order, canon, _top = canonical_pc(nodes, root, removed)
    dag = DAG()
    for i in order:
        kind, ch, _w = canon[i]
        dag.add(i, kind, ch)
    return dag
