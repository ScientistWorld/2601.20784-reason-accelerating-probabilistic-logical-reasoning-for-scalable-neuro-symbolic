#!/usr/bin/env python3
"""Evaluate REASON artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def canonical_method_name(path: Path, payload: dict) -> str:
    declared_name = payload.get("method")
    raw_name = str(declared_name or path.stem)
    normalized = raw_name.strip()
    lower = normalized.lower()
    if lower in {"unpruned_baseline", "baseline", "unpruned"}:
        return "unpruned_dag"
    if declared_name is None and "baseline" in path.stem.lower():
        return "unpruned_dag"
    return normalized


def result_metrics(result: dict) -> dict[str, float]:
    baseline = result["baseline"]
    baseline_regularized = result.get("baseline_regularized", baseline)
    pruned = result.get("pruned", result.get("reason"))
    reason = result["reason"]
    memory_reduction = 100.0 * (float(baseline["memory_units"]) - float(pruned["memory_units"])) / float(baseline["memory_units"])
    edge_reduction = 100.0 * (float(baseline["edges"]) - float(pruned["edges"])) / float(baseline["edges"])
    final_memory_reduction = 100.0 * (
        float(baseline_regularized["memory_units"]) - float(reason["memory_units"])
    ) / float(baseline_regularized["memory_units"])
    final_edge_reduction = 100.0 * (
        float(baseline_regularized["edges"]) - float(reason["edges"])
    ) / float(baseline_regularized["edges"])
    metrics = {
        "memory_reduction_pct": memory_reduction,
        "compression_balance_pct": min(memory_reduction, edge_reduction),
        "edge_reduction_pct": edge_reduction,
        "final_regularized_memory_reduction_pct": final_memory_reduction,
        "final_regularized_edge_reduction_pct": final_edge_reduction,
        "fanin_regularized": 1.0 if float(reason["max_fanin"]) <= 2.0 else 0.0,
        "regularized_memory_overhead_pct": 100.0
        * (float(reason["memory_units"]) - float(pruned["memory_units"]))
        / float(pruned["memory_units"]),
    }
    if "avg_loglik_retention_pct" in result:
        metrics["avg_loglik_retention_pct"] = float(result["avg_loglik_retention_pct"])
    if "avg_loglik_before" in result and "avg_loglik_after" in result:
        metrics["avg_abs_loglik_delta"] = abs(float(result["avg_loglik_after"]) - float(result["avg_loglik_before"]))
    if "semantics_preserved" in result:
        metrics["semantics_preserved"] = float(result["semantics_preserved"])
    if "implication_proof_sound" in result:
        metrics["implication_proof_sound"] = float(result["implication_proof_sound"])
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method-artifact", default="checkpoints/reason_outputs.json")
    parser.add_argument("--baseline-artifact", default="checkpoints/baseline_outputs.json")
    parser.add_argument("--out", default="scoring/scores.json")
    args = parser.parse_args()

    method_path = Path(args.method_artifact)
    baseline_path = Path(args.baseline_artifact)
    method_payload = json.loads(method_path.read_text(encoding="utf-8"))
    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    method_name = canonical_method_name(method_path, method_payload)
    baseline_name = canonical_method_name(baseline_path, baseline_payload)
    scores = {"experiments": {}}
    for exp_name, method_result in method_payload["results"].items():
        scores["experiments"][exp_name] = {
            "results": {
                baseline_name: result_metrics(baseline_payload["results"][exp_name]),
                method_name: result_metrics(method_result),
            }
        }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(scores, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
