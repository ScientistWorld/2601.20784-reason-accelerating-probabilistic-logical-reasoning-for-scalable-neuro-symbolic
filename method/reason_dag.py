"""Unified DAG utilities used by the REASON algorithm passes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    op: str
    inputs: list[str] = field(default_factory=list)
    value: Any = None


class DAG:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add(self, name: str, op: str, inputs: list[str] | None = None, value: Any = None) -> str:
        self.nodes[name] = Node(op=op, inputs=list(inputs or []), value=value)
        return name

    def edge_count(self) -> int:
        return sum(len(n.inputs) for n in self.nodes.values())

    def max_fanin(self) -> int:
        return max((len(n.inputs) for n in self.nodes.values()), default=0)

    def memory_units(self) -> int:
        return len(self.nodes) + self.edge_count()

    def two_input_regularize(self) -> "DAG":
        out = DAG()
        counter = 0
        for name, node in self.nodes.items():
            for child in node.inputs:
                if child not in out.nodes and child in self.nodes:
                    src = self.nodes[child]
                    out.add(child, src.op, [], src.value)
            if len(node.inputs) <= 2:
                out.add(name, node.op, node.inputs, node.value)
                continue
            level = list(node.inputs)
            while len(level) > 2:
                nxt = []
                for idx in range(0, len(level), 2):
                    pair = level[idx : idx + 2]
                    if len(pair) == 1:
                        nxt.append(pair[0])
                    else:
                        mid = f"{name}__regularized_{counter}"
                        counter += 1
                        out.add(mid, node.op, pair, node.value)
                        nxt.append(mid)
                level = nxt
            out.add(name, node.op, level, node.value)
        return out

    def summary(self) -> dict[str, int]:
        return {"nodes": len(self.nodes), "edges": self.edge_count(), "memory_units": self.memory_units(), "max_fanin": self.max_fanin()}
