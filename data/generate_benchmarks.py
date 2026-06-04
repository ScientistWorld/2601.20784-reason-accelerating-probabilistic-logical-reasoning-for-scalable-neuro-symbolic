#!/usr/bin/env python3
"""Generate deterministic symbolic/probabilistic DAG benchmarks.

The paper evaluates REASON on larger neuro-symbolic systems whose full data
and hardware stack are not released. These fixtures preserve the Sec. IV
kernel structure: CNF formulas with implication redundancy, HMMs with rare
transitions, and probabilistic circuits with low-flow branches.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    return [v / total for v in values]


def make_sat(seed: int, variables: int, clauses: int) -> dict:
    rng = random.Random(seed)
    cnf: list[list[int]] = []
    for i in range(1, variables, 2):
        cnf.append([-i, i + 1])
    for _ in range(clauses):
        a = rng.randint(1, variables - 1)
        b = a + 1 if a % 2 == 1 else max(1, a - 1)
        c = rng.randint(1, variables)
        cnf.append([a, b, -c if rng.random() < 0.5 else c])
    return {"variables": variables, "clauses": cnf}


def make_hmm(seed: int, states: int, observations: int, length: int, sequences: int) -> dict:
    rng = random.Random(seed)
    transition = []
    for s in range(states):
        row = [0.001 for _ in range(states)]
        row[s] = 0.77
        row[(s + 1) % states] = 0.22
        transition.append(_normalize(row))
    emission = []
    for s in range(states):
        row = [0.02 for _ in range(observations)]
        row[s % observations] = 0.70
        row[(s + 1) % observations] = 0.20
        emission.append(_normalize(row))
    initial = _normalize([1.0 + (0.15 if s == 0 else 0.0) for s in range(states)])

    samples = []
    for _ in range(sequences):
        z = rng.choices(range(states), initial)[0]
        obs = []
        for _t in range(length):
            obs.append(rng.choices(range(observations), emission[z])[0])
            z = rng.choices(range(states), transition[z])[0]
        samples.append(obs)
    return {"states": states, "observations": observations, "initial": initial, "transition": transition, "emission": emission, "sequences": samples}


def make_pc(seed: int, components: int, dimensions: int, samples: int) -> dict:
    rng = random.Random(seed)
    weights = _normalize([1.0 if k < 3 else 0.08 for k in range(components)])
    means = [[-2.0 + 4.0 * ((k + d) % 3) / 2.0 for d in range(dimensions)] for k in range(components)]
    stdevs = [[0.7 + 0.1 * ((k + d) % 2) for d in range(dimensions)] for k in range(components)]
    observations = []
    for _ in range(samples):
        k = rng.choices(range(components), weights)[0]
        observations.append([rng.gauss(means[k][d], stdevs[k][d]) for d in range(dimensions)])
    return {"weights": weights, "means": means, "stdevs": stdevs, "samples": observations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/reason_benchmarks.json")
    parser.add_argument("--seed", type=int, default=20784)
    parser.add_argument("--sat-vars", type=int, default=28)
    parser.add_argument("--sat-clauses", type=int, default=84)
    parser.add_argument("--hmm-states", type=int, default=12)
    parser.add_argument("--hmm-length", type=int, default=48)
    parser.add_argument("--hmm-sequences", type=int, default=80)
    parser.add_argument("--pc-components", type=int, default=12)
    parser.add_argument("--pc-samples", type=int, default=160)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "sat": make_sat(args.seed, args.sat_vars, args.sat_clauses),
        "hmm": make_hmm(args.seed + 1, args.hmm_states, 6, args.hmm_length, args.hmm_sequences),
        "pc": make_pc(args.seed + 2, args.pc_components, 4, args.pc_samples),
    }
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
