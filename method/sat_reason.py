"""REASON SAT/FOL-style DAG lowering and implication pruning."""

from __future__ import annotations

from collections import defaultdict, deque

from method.reason_dag import DAG


def _neg(lit: int) -> int:
    return -lit


def build_cnf_dag(cnf: list[list[int]]) -> DAG:
    dag = DAG()
    clause_names = []
    for idx, clause in enumerate(cnf):
        literals = []
        for lit in clause:
            name = f"lit_{lit}"
            if name not in dag.nodes:
                dag.add(name, "literal", [], lit)
            literals.append(name)
        cname = f"clause_{idx}"
        dag.add(cname, "or", literals)
        clause_names.append(cname)
    dag.add("formula", "and", clause_names)
    return dag


def implication_graph(cnf: list[list[int]]) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = defaultdict(set)
    for clause in cnf:
        if len(clause) == 2:
            a, b = clause
            graph[_neg(a)].add(b)
            graph[_neg(b)].add(a)
    return graph


def reachable(graph: dict[int, set[int]], start: int) -> set[int]:
    seen = set()
    queue = deque([start])
    while queue:
        item = queue.popleft()
        for nxt in graph.get(item, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def prune_hidden_literals(cnf: list[list[int]]) -> tuple[list[list[int]], int]:
    graph = implication_graph(cnf)
    reach = {lit: reachable(graph, lit) for lit in graph}
    pruned = []
    removed = 0
    for clause in cnf:
        keep = list(clause)
        for a in clause:
            for b in clause:
                # If a implies b, then (a OR b OR rest) is equivalent to
                # (b OR rest); b already covers every satisfying assignment
                # that a can cover.
                if a != b and b in reach.get(a, set()) and a in keep and len(keep) > 1:
                    keep.remove(a)
                    removed += 1
                    break
        pruned.append(keep)
    return pruned, removed


def implication_pruning_is_sound(cnf: list[list[int]], original: list[list[int]], pruned: list[list[int]]) -> bool:
    """Check each removed literal has a proof via the binary-clause implication graph."""
    graph = implication_graph(cnf)
    reach = {lit: reachable(graph, lit) for lit in graph}
    for before, after in zip(original, pruned):
        removed = set(before) - set(after)
        for lit in removed:
            if not any(kept in reach.get(lit, set()) for kept in after):
                return False
    return True


def _simplify(cnf: list[list[int]], assignment: dict[int, bool]) -> list[list[int]] | None:
    simplified = []
    for clause in cnf:
        new_clause = []
        satisfied = False
        for lit in clause:
            var = abs(lit)
            if var not in assignment:
                new_clause.append(lit)
                continue
            value = assignment[var]
            if (lit > 0 and value) or (lit < 0 and not value):
                satisfied = True
                break
        if not satisfied:
            if not new_clause:
                return None
            simplified.append(new_clause)
    return simplified


def _unit_propagate(cnf: list[list[int]], assignment: dict[int, bool]) -> tuple[list[list[int]] | None, dict[int, bool]]:
    changed = True
    while changed:
        changed = False
        for clause in cnf:
            if len(clause) != 1:
                continue
            lit = clause[0]
            var = abs(lit)
            value = lit > 0
            if var in assignment and assignment[var] != value:
                return None, assignment
            if var not in assignment:
                assignment = dict(assignment)
                assignment[var] = value
                simplified = _simplify(cnf, assignment)
                if simplified is None:
                    return None, assignment
                cnf = simplified
                changed = True
                break
    return cnf, assignment


def is_satisfiable(cnf: list[list[int]]) -> bool:
    simplified, assignment = _unit_propagate(cnf, {})
    if simplified is None:
        return False
    if not simplified:
        return True
    lit = min((lit for clause in simplified for lit in clause), key=lambda x: abs(x))
    var = abs(lit)
    for value in (True, False):
        branch_assignment = dict(assignment)
        branch_assignment[var] = value
        branch = _simplify(simplified, branch_assignment)
        if branch is not None and is_satisfiable(branch):
            return True
    return False


def run_sat(instance: dict) -> dict:
    cnf = instance["clauses"]
    before = build_cnf_dag(cnf)
    pruned_cnf, removed = prune_hidden_literals(cnf)
    after_prune = build_cnf_dag(pruned_cnf)
    after = after_prune.two_input_regularize()
    original_sat = is_satisfiable(cnf)
    pruned_sat = is_satisfiable(pruned_cnf)
    proof_sound = implication_pruning_is_sound(cnf, cnf, pruned_cnf)
    return {
        "kernel": "sat",
        "baseline": before.summary(),
        "baseline_regularized": before.two_input_regularize().summary(),
        "pruned": after_prune.summary(),
        "reason": after.summary(),
        "removed_literals": removed,
        "clauses_before": len(cnf),
        "clauses_after": len(pruned_cnf),
        "semantics_preserved": 1.0 if proof_sound and original_sat == pruned_sat else 0.0,
        "implication_proof_sound": 1.0 if proof_sound else 0.0,
        "original_satisfiable": 1.0 if original_sat else 0.0,
        "pruned_satisfiable": 1.0 if pruned_sat else 0.0,
    }
