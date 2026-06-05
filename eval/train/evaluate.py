#!/usr/bin/env python3
"""Visible train-slice scoring for REASON artifacts.

This evaluator reads method-produced JSON artifacts only. It does not import or
execute method code, so any future method can participate by writing the same
artifact structure.
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


def memory_reduction_pct(result: dict[str, Any]) -> float:
    if "memory_reduction_pct" in result:
        return float(result["memory_reduction_pct"])
    baseline = result["baseline"]
    pruned = result.get("pruned", result.get("reason"))
    return 100.0 * (float(baseline["memory_units"]) - float(pruned["memory_units"])) / float(baseline["memory_units"])


def train_metrics(exp_name: str, result: dict[str, Any]) -> dict[str, float]:
    metrics = {"memory_reduction_pct": memory_reduction_pct(result)}
    if exp_name == "sat_implication_pruning":
        metrics["semantics_preserved"] = float(result["semantics_preserved"])
    else:
        metrics["avg_loglik_retention_pct"] = float(result["avg_loglik_retention_pct"])
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", default=[], help="Method artifact JSON. May be repeated.")
    parser.add_argument("--artifact-dir", default="checkpoints", help="Directory to enumerate when no artifacts are passed.")
    parser.add_argument("--out", default="scoring/scores_train.json")
    args = parser.parse_args()

    artifacts = load_artifacts(discover_artifacts(args.artifact, args.artifact_dir))
    scores: dict[str, Any] = {"experiments": {}}
    for exp_name in sorted(EXPERIMENTS):
        exp_results: dict[str, dict[str, float]] = {}
        for method_name, payload in sorted(artifacts.items()):
            if exp_name not in payload["results"]:
                raise KeyError(f"artifact for {method_name!r} is missing experiment {exp_name!r}")
            exp_results[method_name] = train_metrics(exp_name, payload["results"][exp_name])
        scores["experiments"][exp_name] = {"results": exp_results}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scores, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
