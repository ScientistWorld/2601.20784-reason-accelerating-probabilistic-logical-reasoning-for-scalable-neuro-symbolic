#!/usr/bin/env python3
"""Write unpruned DAG artifacts for evaluation pipeline checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from method.hmm_reason import build_hmm_dag, avg_loglik as hmm_loglik
from method.pc_reason import build_pc_dag, avg_loglik as pc_loglik
from method.sat_reason import build_cnf_dag


def wrap(summary: dict, regularized_summary: dict, **extra: float) -> dict:
    out = {
        "baseline": summary,
        "baseline_regularized": regularized_summary,
        "pruned": summary,
        "reason": regularized_summary,
        "memory_reduction_pct": 0.0,
        "edge_reduction_pct": 0.0,
        "final_regularized_memory_reduction_pct": 0.0,
        "final_regularized_edge_reduction_pct": 0.0,
        "fanin_regularized": 1.0 if regularized_summary["max_fanin"] <= 2 else 0.0,
    }
    out.update(extra)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/reason_benchmarks.json")
    parser.add_argument("--out", default="checkpoints/baseline_outputs.json")
    args = parser.parse_args()
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))

    sat_dag = build_cnf_dag(payload["sat"]["clauses"])
    hmm = payload["hmm"]
    hmm_dag = build_hmm_dag(len(hmm["initial"]), len(hmm["sequences"][0]), hmm["transition"])
    hmm_ll = hmm_loglik(hmm["sequences"], hmm["initial"], hmm["transition"], hmm["emission"])
    pc = payload["pc"]
    pc_dag = build_pc_dag(pc["weights"], len(pc["means"][0]))
    pc_ll = pc_loglik(pc["samples"], pc["weights"], pc["means"], pc["stdevs"])

    results = {
        "sat_implication_pruning": wrap(
            sat_dag.summary(),
            sat_dag.two_input_regularize().summary(),
            removed_literals=0,
            semantics_preserved=1.0,
            implication_proof_sound=1.0,
        ),
        "hmm_flow_pruning": wrap(
            hmm_dag.summary(),
            hmm_dag.two_input_regularize().summary(),
            avg_loglik_before=hmm_ll,
            avg_loglik_after=hmm_ll,
            avg_loglik_retention_pct=100.0,
        ),
        "pc_flow_pruning": wrap(
            pc_dag.summary(),
            pc_dag.two_input_regularize().summary(),
            avg_loglik_before=pc_ll,
            avg_loglik_after=pc_ll,
            avg_loglik_retention_pct=100.0,
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"method": "unpruned_baseline", "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
