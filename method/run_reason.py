#!/usr/bin/env python3
"""Run the REASON Sec. IV algorithm passes and write reusable artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from method.hmm_reason import run_hmm
from method.pc_reason import run_pc
from method.sat_reason import run_sat


def add_common_metrics(result: dict) -> dict:
    b = result["baseline"]
    br = result["baseline_regularized"]
    p = result.get("pruned", result["reason"])
    r = result["reason"]
    result["memory_reduction_pct"] = 100.0 * (b["memory_units"] - p["memory_units"]) / b["memory_units"]
    result["edge_reduction_pct"] = 100.0 * (b["edges"] - p["edges"]) / b["edges"]
    result["final_regularized_memory_reduction_pct"] = 100.0 * (br["memory_units"] - r["memory_units"]) / br["memory_units"]
    result["final_regularized_edge_reduction_pct"] = 100.0 * (br["edges"] - r["edges"]) / br["edges"]
    result["fanin_regularized"] = 1.0 if r["max_fanin"] <= 2 else 0.0
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/reason_benchmarks.json")
    parser.add_argument("--out", default="checkpoints/reason_outputs.json")
    parser.add_argument("--prune-fraction", type=float, default=0.30)
    args = parser.parse_args()
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    results = {
        "sat_implication_pruning": add_common_metrics(run_sat(payload["sat"])),
        "hmm_flow_pruning": add_common_metrics(run_hmm(payload["hmm"], args.prune_fraction)),
        "pc_flow_pruning": add_common_metrics(run_pc(payload["pc"], args.prune_fraction)),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"method": "reason_algorithm", "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
