#!/usr/bin/env python3
"""Evaluate REASON artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def result_metrics(result: dict) -> dict[str, float]:
    metrics = {
        "memory_reduction_pct": float(result["memory_reduction_pct"]),
    }
    if "avg_loglik_retention_pct" in result:
        metrics["avg_loglik_retention_pct"] = float(result["avg_loglik_retention_pct"])
    if "semantics_preserved" in result:
        metrics["semantics_preserved"] = float(result["semantics_preserved"])
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method-artifact", default="checkpoints/reason_outputs.json")
    parser.add_argument("--baseline-artifact", default="checkpoints/baseline_outputs.json")
    parser.add_argument("--out", default="scoring/scores.json")
    args = parser.parse_args()

    method_payload = json.loads(Path(args.method_artifact).read_text(encoding="utf-8"))
    baseline_payload = json.loads(Path(args.baseline_artifact).read_text(encoding="utf-8"))
    scores = {"experiments": {}}
    for exp_name, method_result in method_payload["results"].items():
        scores["experiments"][exp_name] = {
            "results": {
                "unpruned_dag": result_metrics(baseline_payload["results"][exp_name]),
                "reason_algorithm": result_metrics(method_result),
            }
        }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(scores, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
