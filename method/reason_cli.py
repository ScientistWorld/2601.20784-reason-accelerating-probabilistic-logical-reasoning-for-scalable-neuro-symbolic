#!/usr/bin/env python3
"""REASON algorithm entry point (the procedure the evaluators call).

    python3 -m method.reason_cli --instance IN.json --out OUT.json

IN.json is one kernel instance (``task`` = sat | hmm | pc) with the model,
its calibration data and the memory budgets; OUT.json receives the
transformed model(s).  Stage 1 (unified DAG), Stage 2 (adaptive pruning) and
Stage 3 (two-input regularisation, used for memory accounting) are in
method/reason_dag.py and the per-kernel modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from method.hmm_reason import run_hmm
from method.pc_reason import run_pc
from method.sat_reason import run_sat

RUNNERS = {"sat": run_sat, "hmm": run_hmm, "pc": run_pc}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    instance = json.loads(Path(args.instance).read_text(encoding="utf-8"))
    result = RUNNERS[instance["task"]](instance)
    Path(args.out).write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
