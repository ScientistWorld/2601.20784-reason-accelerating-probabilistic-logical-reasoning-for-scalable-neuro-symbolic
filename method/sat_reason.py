"""REASON SAT/FOL pruning via the binary implication graph (Sec. IV-B a).

Each binary clause (l v l') induces implication edges -l -> l' and -l' -> l.
Reachability over this graph (depth-first traversal from every literal)
gives the "always implied" relation.  Two kinds of redundant literals are
then removed from clauses, without changing the set of models:

* hidden literals: if a -> b and both a and b are in clause C, then
  (a v b v rest) == (b v rest) under the formula, so a is dropped.  (The
  paper's text names the implied literal as the one to drop, which would not
  preserve semantics; the sound direction drops the implying literal.)
* failed literals: if l -> -l then every model sets l false, so l is
  dropped from every clause that still has another literal.

Both rules only shrink clauses, so the result is logically equivalent to the
input formula (each removal is justified by implications of the input).
"""

from __future__ import annotations

from collections import defaultdict


def implication_graph(clauses) -> dict:
    graph: dict = defaultdict(set)
    for clause in clauses:
        if len(clause) == 2:
            a, b = clause
            graph[-a].add(b)
            graph[-b].add(a)
    return graph


def reachable(graph, start: int) -> set:
    seen = set()
    stack = [start]
    while stack:
        lit = stack.pop()
        for nxt in graph.get(lit, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def prune_redundant_literals(clauses) -> tuple[list, dict]:
    graph = implication_graph(clauses)
    reach = {lit: reachable(graph, lit) for lit in list(graph)}
    failed = {lit for lit, r in reach.items() if -lit in r}
    out = []
    stats = {"hidden_literals": 0, "failed_literals": 0, "failed_literal_ids": len(failed)}
    for clause in clauses:
        keep = list(dict.fromkeys(clause))
        for a in list(keep):
            if len(keep) <= 1:
                break
            if a in failed:
                keep.remove(a)
                stats["failed_literals"] += 1
                continue
            implied = reach.get(a)
            if implied and any(b != a and b in implied for b in keep):
                keep.remove(a)
                stats["hidden_literals"] += 1
        out.append(keep)
    return out, stats


def run_sat(instance: dict) -> dict:
    clauses = [list(c) for c in instance["clauses"]]
    pruned, stats = prune_redundant_literals(clauses)
    return {"clauses": pruned, "stats": stats}
