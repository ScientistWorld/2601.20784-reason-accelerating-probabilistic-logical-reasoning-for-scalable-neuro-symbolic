#!/usr/bin/env python3
"""Rank every audited run with the gym's rule and estimate paired test noise.

rank(a) = sum_e weight_e * sum_m |coef_m| * dir_m * (a_m - ref_m) / std_m
std_m   = population std of metric m over the audited runs (one per name);
          'pair' uses only {reference, candidate}.  Missing values are skipped.
"""
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "redteam" / "hardened" / "results"
REF_NAME = "reason_algorithm"
cfg = json.loads((ROOT / "scoring" / "reference.json").read_text())["experiments"]

attempts, status, group_of = {}, {}, {}
for path in sorted(RES.glob("*_scores_test.json")):
    group = path.name[: -len("_scores_test.json")]
    data = json.loads(path.read_text())
    for exp, ed in data["experiments"].items():
        for name, metrics in ed["results"].items():
            key = name if group in ("quality",) or name != REF_NAME else f"{name}@{group}"
            attempts.setdefault(key, {})[exp] = metrics
            group_of[key] = group
    for name, st in data.get("_status", {}).items():
        key = name if group in ("quality",) or name != REF_NAME else f"{name}@{group}"
        status[key] = st
ref = attempts[REF_NAME]
cohort = [k for k in attempts if not k.startswith(REF_NAME + "@")]


def stds(names):
    out = {}
    for exp, ec in cfg.items():
        for m in ec["metrics"]:
            vals = [attempts[n][exp][m] for n in names if m in attempts[n].get(exp, {})]
            out[(exp, m)] = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    return out


def rank(name, sd):
    total = 0.0
    for exp, ec in cfg.items():
        for m, mc in ec["metrics"].items():
            a, r, s = attempts[name].get(exp, {}).get(m), ref.get(exp, {}).get(m), sd[(exp, m)]
            if a is None or r is None or not s:
                continue
            d = 1.0 if mc["higher_is_better"] else -1.0
            total += ec["weight"] * abs(mc["coefficient"]) * d * (a - r) / s
    return total


sd_cohort = stds(cohort)
rows = {}
for name in attempts:
    rows[name] = {"group": group_of[name], "failed": status.get(name, {}).get("failed"),
                  "reason": status.get(name, {}).get("reason", ""), "metrics": attempts[name],
                  "rank_cohort": rank(name, sd_cohort),
                  "rank_pair": rank(name, stds([REF_NAME, name]))}

# paired noise from per-sample records (quality group)
noise = {}
det_path = RES / "quality_test_details.json"
if det_path.exists():
    det = json.loads(det_path.read_text())
    refd = det.get(REF_NAME, {}).get("details", {})
    for name, st in det.items():
        if name == REF_NAME or st.get("failed"):
            continue
        noise[name] = {}
        for exp, rows_c in st["details"].items():
            rows_r = refd.get(exp, [])
            if exp.startswith("sat"):
                diffs = [c["memory_reduction_pct"] - r["memory_reduction_pct"] for c, r in zip(rows_c, rows_r)]
                se = statistics.stdev(diffs) / math.sqrt(len(diffs)) if len(diffs) > 1 else 0.0
                noise[name][exp] = {"memory_reduction_pct": {"diff": statistics.mean(diffs), "se_instances": se}}
                continue
            metrics = cfg[exp]["metrics"]
            names = [m for m in metrics]
            noise[name][exp] = {}
            for b, m in enumerate(names):
                inst_diffs, se2 = [], 0.0
                for c, r in zip(rows_c, rows_r):
                    d = [x - y for x, y in zip(c["deltas"][b], r["deltas"][b])]
                    inst_diffs.append(c["retention"][b] - r["retention"][b])
                    se2 += (r["retention"][b] * statistics.stdev(d) / math.sqrt(len(d))) ** 2
                k = len(inst_diffs)
                noise[name][exp][m] = {
                    "diff": statistics.mean(inst_diffs),
                    "se_samples_paired": math.sqrt(se2) / k,
                    "se_instances": statistics.stdev(inst_diffs) / math.sqrt(k) if k > 1 else 0.0,
                    "per_instance_diff": inst_diffs}

summary = {"formula": "sum_e weight_e * sum_m |coef_m| * dir_m * (x - ref) / pstdev_m", "reference": REF_NAME,
           "cohort": cohort, "metric_std_cohort": {f"{e}.{m}": v for (e, m), v in sd_cohort.items()},
           "runs": rows, "paired_noise_vs_reference": noise}
(RES.parent / "summary.json").write_text(json.dumps(summary, indent=2))
for name, r in sorted(rows.items(), key=lambda kv: -kv[1]["rank_cohort"]):
    flag = "FAILED" if r["failed"] else "ok"
    print(f"{name:32s} {r['group']:10s} {flag:6s} cohort={r['rank_cohort']:+.3f} pair={r['rank_pair']:+.3f} {r['reason'][:70]}")
