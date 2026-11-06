# REASON: Accelerating Probabilistic Logical Reasoning for Scalable Neuro-Symbolic Intelligence

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2601.20784"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2601.20784-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2601.20784](https://arxiv.org/abs/2601.20784) |
| **Domain** | Neuro-symbolic AI / computer architecture |
| **TL;DR** | REASON compiles logical and probabilistic reasoning into unified DAGs, prunes low-value structure, regularizes the graph for tree hardware, and reports large efficiency gains. |

## Summary

The paper argues that symbolic and probabilistic reasoning stages are a major efficiency bottleneck in neuro-symbolic systems. REASON addresses this with a cross-layer design: algorithmic DAG unification/pruning/regularization, a reconfigurable tree-based accelerator, and GPU-coprocessor integration. The reproduction focuses on the algorithmic layer because full hardware synthesis and cycle-accurate accelerator integration are outside this benchmark environment.

## Problem

Can symbolic and probabilistic reasoning kernels in neuro-symbolic systems be transformed into compact executable graph representations while preserving the reasoning result?

## The paper's method

REASON is an algorithm-hardware co-design framework for accelerating probabilistic logical reasoning in neuro-symbolic AI systems.

## Key results of the paper

- Table IV reports comparable task performance after algorithm optimization with an average 31.7% memory reduction.
- The hardware evaluation reports about 50.65x speedup over Orin NX and 11.98x over RTX GPU, plus two-orders-of-magnitude energy-efficiency gains.
- The accelerator is reported as 6 mm2 and 2.12 W at 28 nm.

## Run it

```bash
pip install sciworld
sw research 2601.20784 --mode innovate --agent claude-code
sw evaluate 2601.20784
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

