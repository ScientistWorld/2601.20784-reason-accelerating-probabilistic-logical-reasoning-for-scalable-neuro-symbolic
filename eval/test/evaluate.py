#!/usr/bin/env python3
"""Held-out test-slice scoring for REASON artifacts.

The test slice scores the same method entries seen in scores_train.json when
that file exists, but computes held-out structural metrics from the artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPERIMENTS = {
    "sat_implication_pruning",
    "hmm_flow_pruning",
    "pc_flow_pruning",
}


def canonical_method_name(path: Path, payload: dict[str, Any]) -> str:
    declared_name = payload.get("method")
    raw_name = str(declared_name or path.stem)
    normalized = raw_name.strip()
    lower = normalized.lower()
    if lower in {"unpruned_baseline", "baseline", "unpruned"}:
        return "unpruned_dag"
    if declared_name is None and "baseline" in path.stem.lower():
        return "unpruned_dag"
    return normalized


def discover_artifacts(paths: list[str], artifact_dir: str) -> list[Path]:
    if paths:
        return [Path(p) for p in paths]
    root = Path(artifact_dir)
    return sorted(p for p in root.glob("*.json") if p.is_file())


def load_artifacts(paths: list[Path]) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("results"), dict):
            continue
        name = canonical_method_name(path, payload)
        if name in artifacts:
            raise ValueError(f"multiple artifacts map to method {name!r}")
        artifacts[name] = payload
    if not artifacts:
        raise ValueError("no method artifacts with a top-level 'results' object were found")
    return artifacts


def reduced_summary(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("pruned", result.get("reason"))


def method_names_from_train_scores(path: str) -> list[str] | None:
    train_path = Path(path)
    if not train_path.exists():
        return None
    payload = json.loads(train_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for exp_payload in payload.get("experiments", {}).values():
        names.update(exp_payload.get("results", {}).keys())
    return sorted(names)


def edge_reduction_pct(result: dict[str, Any]) -> float:
    baseline = result["baseline"]
    pruned = reduced_summary(result)
    return 100.0 * (float(baseline["edges"]) - float(pruned["edges"])) / float(baseline["edges"])


def fanin_regularized(result: dict[str, Any]) -> float:
    reason = result["reason"]
    return 1.0 if float(reason["max_fanin"]) <= 2.0 else 0.0


def regularized_memory_overhead_pct(result: dict[str, Any]) -> float:
    baseline = result["baseline"]
    reason = result["reason"]
    return 100.0 * (float(reason["memory_units"]) - float(baseline["memory_units"])) / float(baseline["memory_units"])


def avg_abs_loglik_delta(result: dict[str, Any]) -> float:
    return abs(float(result["avg_loglik_after"]) - float(result["avg_loglik_before"]))


def test_metrics(exp_name: str, result: dict[str, Any]) -> dict[str, float]:
    metrics = {
        "edge_reduction_pct": edge_reduction_pct(result),
        "fanin_regularized": fanin_regularized(result),
        "regularized_memory_overhead_pct": regularized_memory_overhead_pct(result),
    }
    if exp_name == "sat_implication_pruning":
        metrics["semantics_preserved"] = float(result["semantics_preserved"])
    else:
        metrics["avg_loglik_retention_pct"] = float(result["avg_loglik_retention_pct"])
        metrics["avg_abs_loglik_delta"] = avg_abs_loglik_delta(result)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", default=[], help="Method artifact JSON. May be repeated.")
    parser.add_argument("--artifact-dir", default="checkpoints", help="Directory to enumerate when no artifacts are passed.")
    parser.add_argument("--train-scores", default="scoring/scores_train.json")
    parser.add_argument("--out", default="scoring/scores_test.json")
    args = parser.parse_args()

    artifacts = load_artifacts(discover_artifacts(args.artifact, args.artifact_dir))
    train_method_names = method_names_from_train_scores(args.train_scores)
    if train_method_names is None:
        method_names = sorted(artifacts)
    else:
        missing = [name for name in train_method_names if name not in artifacts]
        if missing:
            raise KeyError(f"missing artifacts for train-scored methods: {', '.join(missing)}")
        method_names = train_method_names

    scores: dict[str, Any] = {"slice": "test", "experiments": {}}
    for exp_name in sorted(EXPERIMENTS):
        exp_results: dict[str, dict[str, float]] = {}
        for method_name in method_names:
            payload = artifacts[method_name]
            if exp_name not in payload["results"]:
                raise KeyError(f"artifact for {method_name!r} is missing experiment {exp_name!r}")
            exp_results[method_name] = test_metrics(exp_name, payload["results"][exp_name])
        scores["experiments"][exp_name] = {"results": exp_results}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scores, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
