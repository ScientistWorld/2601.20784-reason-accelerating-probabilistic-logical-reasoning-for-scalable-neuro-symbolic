"""Evaluator-side kernels: validation, DAG memory accounting, fidelity.

Nothing here trusts a number written by a method.  Every scored quantity is
recomputed from the transformed model a method returns:

* the reasoning DAG is compiled by the evaluator from the model,
* fan-in > 2 nodes are expanded into balanced binary trees (two-input form)
  and memory = nodes + edges of that final DAG,
* logical equivalence of CNFs is certified by unit propagation with a
  bounded DPLL fallback,
* probabilistic models are checked for proper normalisation (and, for
  circuits, smoothness and decomposability) before their likelihood on
  held-out data is computed.

Any violation raises ``Invalid``.
"""

from __future__ import annotations

import math
from collections import defaultdict


class Invalid(Exception):
    """The transformed model violates a hard constraint of the benchmark."""


NORM_TOL = 1e-6
MAX_NODES = 400_000
MAX_EDGES = 2_000_000


def reg_cost(fanin: int) -> int:
    """Memory (nodes + edges) of one node after two-input regularisation.

    A node with k > 2 inputs becomes a balanced binary tree of k - 1 two-input
    nodes with 2(k - 1) edges; nodes with k <= 2 inputs are unchanged.
    """
    if fanin <= 0:
        return 1
    if fanin == 1:
        return 2
    return 3 * (fanin - 1)


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ============================================================================
# SAT / CNF
# ============================================================================

def canonical_cnf(clauses, num_vars: int) -> list[tuple[int, ...]]:
    if not isinstance(clauses, list):
        raise Invalid("clauses must be a list")
    seen = set()
    out = []
    for clause in clauses:
        if not isinstance(clause, list):
            raise Invalid("each clause must be a list of literals")
        lits = set()
        for lit in clause:
            if not isinstance(lit, int) or isinstance(lit, bool) or lit == 0 or abs(lit) > num_vars:
                raise Invalid(f"literal {lit!r} is not over variables 1..{num_vars}")
            lits.add(lit)
        if any(-l in lits for l in lits):
            continue  # tautology
        key = tuple(sorted(lits))
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def cnf_memory(clauses: list[tuple[int, ...]]) -> int:
    """Final two-input DAG memory: literal leaves, clause OR nodes, formula AND."""
    leaves = {lit for c in clauses for lit in c}
    total = len(leaves)
    for c in clauses:
        total += reg_cost(len(c))
    total += reg_cost(len(clauses))
    return total


class CNF:
    """Clause database with unit propagation and bounded DPLL."""

    def __init__(self, clauses: list[tuple[int, ...]]):
        self.clauses = clauses
        self.occ: dict[int, list[int]] = defaultdict(list)
        for idx, c in enumerate(clauses):
            for lit in c:
                self.occ[lit].append(idx)
        self.units = [c[0] for c in clauses if len(c) == 1]
        self.has_empty = any(len(c) == 0 for c in clauses)
        self.by_lit: dict[int, list[frozenset]] = defaultdict(list)
        for c in clauses:
            if c:
                self.by_lit[c[0]].append(frozenset(c))

    def has_subset_of(self, clause: tuple[int, ...]) -> bool:
        s = set(clause)
        for lit in clause:
            for d in self.by_lit.get(lit, ()):
                if d <= s:
                    return True
        return False

    def propagate(self, assumptions) -> tuple[bool, dict[int, bool]]:
        """Return (conflict, assignment) after unit propagation."""
        if self.has_empty:
            return True, {}
        val: dict[int, bool] = {}
        queue: list[int] = []

        def assign(lit: int) -> bool:
            v = abs(lit)
            want = lit > 0
            if v in val:
                return val[v] == want
            val[v] = want
            queue.append(lit)
            return True

        for lit in list(assumptions) + self.units:
            if not assign(lit):
                return True, val
        clauses = self.clauses
        while queue:
            lit = queue.pop()
            for ci in self.occ.get(-lit, ()):
                unassigned = None
                n_un = 0
                sat = False
                for l2 in clauses[ci]:
                    v2 = abs(l2)
                    if v2 in val:
                        if val[v2] == (l2 > 0):
                            sat = True
                            break
                    else:
                        n_un += 1
                        unassigned = l2
                        if n_un > 1:
                            break
                if sat or n_un > 1:
                    continue
                if n_un == 0:
                    return True, val
                if not assign(unassigned):
                    return True, val
        return False, val

    def _dpll(self, val: dict[int, bool], budget: list[int]) -> str:
        budget[0] -= 1
        if budget[0] < 0:
            return "unknown"
        # branch on a free literal of the most constrained unsatisfied clause
        branch = None
        best = None
        for c in self.clauses:
            sat = False
            free = None
            n_free = 0
            for l2 in c:
                v2 = abs(l2)
                if v2 in val:
                    if val[v2] == (l2 > 0):
                        sat = True
                        break
                else:
                    n_free += 1
                    if free is None:
                        free = l2
            if not sat:
                if free is None:
                    return "unsat"
                if best is None or n_free < best:
                    best = n_free
                    branch = free
                    if n_free <= 2:
                        break
        if branch is None:
            return "sat"
        any_unknown = False
        for lit in (branch, -branch):
            conflict, val2 = self.propagate(list(_as_lits(val)) + [lit])
            if conflict:
                continue
            res = self._dpll(val2, budget)
            if res == "sat":
                return "sat"
            if res == "unknown":
                any_unknown = True
        return "unknown" if any_unknown else "unsat"

    def entails(self, clause: tuple[int, ...], budget: list[int]) -> str:
        """'yes' if clauses |= clause, 'no' if a counter-model exists, else 'unknown'."""
        if self.has_subset_of(clause):
            return "yes"
        conflict, val = self.propagate([-l for l in clause])
        if conflict:
            return "yes"
        res = self._dpll(val, budget)
        return {"unsat": "yes", "sat": "no"}.get(res, "unknown")


def _as_lits(val: dict[int, bool]):
    for v, b in val.items():
        yield v if b else -v


def check_equivalent(original: list[tuple[int, ...]], candidate: list[tuple[int, ...]],
                     budget_nodes: int = 60_000) -> None:
    """Raise Invalid unless candidate and original have exactly the same models."""
    budget = [budget_nodes]
    f_orig = CNF(original)
    f_cand = CNF(candidate)
    for c in candidate:
        res = f_orig.entails(c, budget)
        if res != "yes":
            raise Invalid(f"output clause {list(c)} is not entailed by the input formula ({res})")
    for c in original:
        res = f_cand.entails(c, budget)
        if res != "yes":
            raise Invalid(f"input clause {list(c)} is not entailed by the output formula ({res})")


def score_sat(instance: dict, output: dict) -> dict:
    n = instance["num_vars"]
    original = canonical_cnf(instance["clauses"], n)
    if not isinstance(output, dict) or "clauses" not in output:
        raise Invalid("SAT output must be an object with a 'clauses' list")
    cand = canonical_cnf(output["clauses"], n)
    check_equivalent(original, cand)
    m0 = cnf_memory(original)
    m1 = cnf_memory(cand)
    return {"memory_before": m0, "memory_after": m1,
            "memory_reduction_pct": 100.0 * (m0 - m1) / m0}


# ============================================================================
# HMM
# ============================================================================

def _matrix(x, rows: int | None, cols: int | None, name: str) -> list[list[float]]:
    if not isinstance(x, list) or (rows is not None and len(x) != rows):
        raise Invalid(f"{name} has the wrong number of rows")
    out = []
    for row in x:
        if not isinstance(row, list) or (cols is not None and len(row) != cols):
            raise Invalid(f"{name} has a row of the wrong length")
        for v in row:
            if not _finite(v) or v < 0.0 or v > 1.0 + NORM_TOL:
                raise Invalid(f"{name} has an entry outside [0, 1]: {v!r}")
        out.append([float(v) for v in row])
    return out


def hmm_validate(model, num_symbols: int, horizon: int) -> dict:
    if not isinstance(model, dict):
        raise Invalid("HMM model must be an object")
    init = model.get("initial")
    if not isinstance(init, list) or not init:
        raise Invalid("HMM initial must be a non-empty list")
    h = len(init)
    if h > 5000:
        raise Invalid("HMM has too many states")
    init = _matrix([init], 1, h, "initial")[0]
    trans = _matrix(model.get("transition"), h, h, "transition")
    emit = _matrix(model.get("emission"), h, num_symbols, "emission")
    if abs(sum(init) - 1.0) > NORM_TOL:
        raise Invalid("initial distribution does not sum to 1")
    alive_steps = hmm_alive(init, trans, horizon)
    used = set().union(*alive_steps)
    for j in sorted(used):
        if abs(sum(emit[j]) - 1.0) > NORM_TOL:
            raise Invalid(f"emission row of reachable state {j} does not sum to 1")
        if abs(sum(trans[j]) - 1.0) > NORM_TOL:
            raise Invalid(f"transition row of reachable state {j} does not sum to 1")
    return {"initial": init, "transition": trans, "emission": emit, "alive": alive_steps}


def hmm_alive(init, trans, horizon: int) -> list[set[int]]:
    succ = [[j for j, v in enumerate(row) if v > 0.0] for row in trans]
    cur = {j for j, v in enumerate(init) if v > 0.0}
    steps = [cur]
    for _ in range(1, horizon):
        nxt = set()
        for i in cur:
            nxt.update(succ[i])
        cur = nxt
        steps.append(cur)
    return steps


def hmm_memory(model: dict, horizon: int) -> int:
    """Two-input memory of the HMM unrolled over ``horizon`` steps.

    Step t has, per live state j: an emission sum node over observation
    indicator leaves (one edge per nonzero emission entry); for t > 1 a sum
    node over live predecessors (one edge per nonzero transition) and a
    product node (sum x emission); for t = 1 a weighted initial node.  The
    observation indicators used at step t are leaves; a root sums the last
    step.
    """
    trans = model["transition"]
    emit = model["emission"]
    alive = model["alive"]
    e_nnz = [sum(1 for v in row if v > 0.0) for row in emit]
    e_sym = [frozenset(o for o, v in enumerate(row) if v > 0.0) for row in emit]
    succ = [[j for j, v in enumerate(row) if v > 0.0] for row in trans]
    total = 0
    prev: set[int] = set()
    for t in range(horizon):
        cur = alive[t]
        if t == 0:
            total += reg_cost(1) * len(cur)
        else:
            fan: dict[int, int] = defaultdict(int)
            for i in prev:
                for j in succ[i]:
                    fan[j] += 1
            for j in cur:
                total += reg_cost(fan[j]) + reg_cost(2)
        syms = set()
        for j in cur:
            total += reg_cost(e_nnz[j])
            syms |= e_sym[j]
        total += len(syms)
        prev = cur
    total += reg_cost(len(prev))
    return total


def hmm_loglik(model: dict, seqs: list[list[int]]) -> list[float]:
    """Exact per-sequence log-likelihood (forward algorithm, vectorised over sequences)."""
    init = model["initial"]
    trans = model["transition"]
    emit = model["emission"]
    h = len(init)
    n = len(seqs)
    length = len(seqs[0])
    edges = [(i, j, v) for i, row in enumerate(trans) for j, v in enumerate(row) if v > 0.0]
    logp = [0.0] * n
    dead = [False] * n
    obs0 = [s[0] for s in seqs]
    alpha = [[init[j] * emit[j][o] for o in obs0] if init[j] > 0.0 else None for j in range(h)]
    for t in range(length):
        if t > 0:
            obs = [s[t] for s in seqs]
            new: list = [None] * h
            for i, j, v in edges:
                a = alpha[i]
                if a is None:
                    continue
                cur = new[j]
                if cur is None:
                    new[j] = [v * x for x in a]
                else:
                    new[j] = [c + v * x for c, x in zip(cur, a)]
            for j in range(h):
                if new[j] is not None:
                    ej = emit[j]
                    new[j] = [x * ej[o] for x, o in zip(new[j], obs)]
            alpha = new
        live = [a for a in alpha if a is not None]
        scale = [sum(col) for col in zip(*live)] if live else [0.0] * n
        inv = []
        for s in range(n):
            c = scale[s]
            if c > 0.0 and not dead[s]:
                logp[s] += math.log(c)
                inv.append(1.0 / c)
            else:
                dead[s] = True
                inv.append(0.0)
        alpha = [None if a is None else [x * w for x, w in zip(a, inv)] for a in alpha]
    return [-math.inf if dead[s] else logp[s] for s in range(n)]


# ============================================================================
# Probabilistic circuits
# ============================================================================

def pc_validate(model, num_vars: int) -> dict:
    """Validate a circuit and return its canonical reachable structure.

    Canonical form drops zero-weight edges and collapses single-input sum /
    product nodes (they are identities).  Validation covers every node
    reachable from the root.
    """
    if not isinstance(model, dict):
        raise Invalid("circuit must be an object with 'nodes' and 'root'")
    nodes = model.get("nodes")
    root = model.get("root")
    if not isinstance(nodes, list) or not nodes or len(nodes) > MAX_NODES:
        raise Invalid("circuit 'nodes' must be a non-empty list (bounded size)")
    if not isinstance(root, int) or isinstance(root, bool) or not 0 <= root < len(nodes):
        raise Invalid("circuit 'root' must index a node")
    # reachability (children must have smaller ids => acyclic)
    reach = [False] * len(nodes)
    reach[root] = True
    n_edges = 0
    for idx in range(root, -1, -1):
        if not reach[idx]:
            continue
        node = nodes[idx]
        if not isinstance(node, list) or not node:
            raise Invalid(f"node {idx} is malformed")
        kind = node[0]
        if kind == "leaf":
            continue
        if kind not in ("sum", "prod") or len(node) < 2 or not isinstance(node[1], list) or not node[1]:
            raise Invalid(f"node {idx} is malformed")
        for c in node[1]:
            if not isinstance(c, int) or isinstance(c, bool) or not 0 <= c < idx:
                raise Invalid(f"node {idx} has child {c!r} that is not an earlier node")
            reach[c] = True
        n_edges += len(node[1])
        if n_edges > MAX_EDGES:
            raise Invalid("circuit has too many edges")

    scope: dict[int, int] = {}
    rep: dict[int, int] = {}
    canon: dict[int, tuple] = {}
    for idx in range(root + 1):
        if not reach[idx]:
            continue
        node = nodes[idx]
        kind = node[0]
        if kind == "leaf":
            if len(node) != 3 or not isinstance(node[1], int) or isinstance(node[1], bool) \
                    or not 0 <= node[1] < num_vars or not _finite(node[2]) or not 0.0 <= node[2] <= 1.0:
                raise Invalid(f"leaf {idx} must be ['leaf', var, p] with p in [0, 1]")
            scope[idx] = 1 << node[1]
            rep[idx] = idx
            canon[idx] = ("leaf", node[1], float(node[2]))
        elif kind == "prod":
            if len(node) != 2:
                raise Invalid(f"product {idx} is malformed")
            acc = 0
            for c in node[1]:
                if acc & scope[c]:
                    raise Invalid(f"product {idx} is not decomposable")
                acc |= scope[c]
            scope[idx] = acc
            ch = [rep[c] for c in node[1]]
            if len(ch) == 1:
                rep[idx] = ch[0]
            else:
                rep[idx] = idx
                canon[idx] = ("prod", ch)
        else:
            if len(node) != 3 or not isinstance(node[2], list) or len(node[2]) != len(node[1]):
                raise Invalid(f"sum {idx} must be ['sum', children, weights]")
            ws = node[2]
            if any(not _finite(w) or w < 0.0 for w in ws):
                raise Invalid(f"sum {idx} has a negative or non-finite weight")
            if abs(sum(ws) - 1.0) > NORM_TOL:
                raise Invalid(f"sum {idx} weights do not sum to 1")
            s0 = scope[node[1][0]]
            if any(scope[c] != s0 for c in node[1]):
                raise Invalid(f"sum {idx} is not smooth")
            scope[idx] = s0
            pairs = [(rep[c], float(w)) for c, w in zip(node[1], ws) if w > 0.0]
            if len(pairs) == 1:
                rep[idx] = pairs[0][0]
            else:
                rep[idx] = idx
                canon[idx] = ("sum", [c for c, _ in pairs], [w for _, w in pairs])
    if scope[root] != (1 << num_vars) - 1:
        raise Invalid("circuit root does not cover every variable")
    top = rep[root]
    keep = set()
    stack = [top]
    while stack:
        i = stack.pop()
        if i in keep:
            continue
        keep.add(i)
        if canon[i][0] != "leaf":
            stack.extend(canon[i][1])
    order = sorted(keep)
    return {"order": order, "nodes": {i: canon[i] for i in order}, "root": top}


def pc_memory(circ: dict) -> int:
    total = 0
    for i in circ["order"]:
        node = circ["nodes"][i]
        total += reg_cost(0 if node[0] == "leaf" else len(node[1]))
    return total


def pc_loglik(circ: dict, samples: list[str], batch: int = 600) -> list[float]:
    out: list[float] = []
    order = circ["order"]
    nodes = circ["nodes"]
    root = circ["root"]
    last_use: dict[int, int] = {}
    for i in order:
        node = nodes[i]
        if node[0] != "leaf":
            for c in node[1]:
                last_use[c] = i
    for start in range(0, len(samples), batch):
        chunk = samples[start:start + batch]
        cols: dict[int, list[int]] = {}
        val: dict[int, list[float]] = {}
        for i in order:
            node = nodes[i]
            if node[0] == "leaf":
                v = node[1]
                if v not in cols:
                    cols[v] = [1 if x[v] == "1" else 0 for x in chunk]
                p = node[2]
                q = 1.0 - p
                val[i] = [p if b else q for b in cols[v]]
            elif node[0] == "prod":
                ch = node[1]
                acc = val[ch[0]]
                for c in ch[1:]:
                    acc = [a * b for a, b in zip(acc, val[c])]
                val[i] = acc
            else:
                ch, ws = node[1], node[2]
                w0 = ws[0]
                acc = [w0 * a for a in val[ch[0]]]
                for c, w in zip(ch[1:], ws[1:]):
                    acc = [a + w * b for a, b in zip(acc, val[c])]
                val[i] = acc
            if node[0] != "leaf":
                for c in node[1]:
                    if last_use.get(c) == i and c != root:
                        val.pop(c, None)
        out.extend(math.log(p) if p > 0.0 else -math.inf for p in val[root])
    return out
