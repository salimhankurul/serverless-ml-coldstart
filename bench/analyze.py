"""Parse raw driver logs (JSONL) into per-invocation rows, a per-configuration summary
row (Table 1 / Table 2 fields) and the measured cost at list price.

Usage: python bench/analyze.py data/raw/*.jsonl --out-dir data/processed
"""
import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

FIELDS = {
    "duration_ms": r"Duration: ([\d.]+) ms",
    "billed_ms": r"Billed Duration: ([\d.]+) ms",
    "memory_mb": r"Memory Size: (\d+) MB",
    "max_memory_used_mb": r"Max Memory Used: (\d+) MB",
    "init_ms": r"Init Duration: ([\d.]+) ms",
}
SEED = 20261118
N_BOOT = 10_000
TARGET = {"cold_p50_ms": 2000.0, "warm_p95_ms": 200.0}   # RQ3 target T (registered)
COLD_SHARES = (0.01, 0.10)


def parse_report(line):
    out = {}
    for key, pat in FIELDS.items():
        # "Duration:" also matches inside "Billed Duration:" / "Init Duration:" -> anchor on tab/start
        if key == "duration_ms":
            m = re.search(r"(?:^|\t)Duration: ([\d.]+) ms", line)
        else:
            m = re.search(pat, line)
        out[key] = float(m.group(1)) if m else None
    return out


def boot_ci_median(x, rng):
    x = np.asarray(x)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    meds = np.median(x[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--prices", default="bench/prices.json")
    args = ap.parse_args()
    prices = json.loads(Path(args.prices).read_text())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    rows = []
    for path in args.raw:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            rep = parse_report(rec["report_line"]) if rec.get("report_line") else {k: None for k in FIELDS}
            gb_s_price = prices["gb_second_usd"][rec["architecture"]]
            cost = None
            if rep["billed_ms"] is not None:
                cost = (rep["billed_ms"] / 1000) * (rep["memory_mb"] / 1024) * gb_s_price \
                    + prices["request_usd_per_million"] / 1e6
            resp = {}
            try:
                resp = json.loads(rec.get("response") or "{}")
            except json.JSONDecodeError:
                pass
            rows.append({
                "run_id": rec["run_id"], "config_id": rec["config_id"], "seq": rec["seq"],
                "phase": rec["phase"], "utc": rec["utc"], "request_id": rec["request_id"],
                "architecture": rec["architecture"], "function_error": rec.get("function_error") or "",
                "client_ms": rec["client_ms"], **rep,
                "cold_start_ms": (rep["init_ms"] + rep["duration_ms"]) if rep["init_ms"] is not None else None,
                "billed_includes_init": (rep["billed_ms"] >= math.floor(rep["init_ms"] + rep["duration_ms"]))
                    if rep["init_ms"] is not None else None,
                "cost_usd": cost,
                "fn_import_ms": resp.get("import_ms"), "fn_load_ms": resp.get("load_ms"),
                "fn_infer_ms": resp.get("infer_ms"), "ort_version": resp.get("ort_version"),
            })

    inv_path = out_dir / "invocations.csv"
    with inv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    by_cfg = defaultdict(list)
    for r in rows:
        by_cfg[r["config_id"]].append(r)

    summaries = []
    for cfg, rs in by_cfg.items():
        cold = [r for r in rs if r["phase"] == "cold"]
        warm = [r for r in rs if r["phase"] == "warm"]
        cold_ms = np.array([r["cold_start_ms"] for r in cold])
        warm_ms = np.array([r["duration_ms"] for r in warm])
        lo, hi = boot_ci_median(cold_ms, rng)
        cold_cost = float(np.mean([r["cost_usd"] for r in cold]))
        warm_cost = float(np.mean([r["cost_usd"] for r in warm]))
        s = {
            "config_id": cfg,
            "architecture": rs[0]["architecture"],
            "memory_mb": int(rs[0]["memory_mb"]),
            "n_cold": len(cold),
            "n_cold_attempts_without_init": sum(r["phase"] == "cold_attempt_without_init" for r in rs),
            "n_warm": len(warm),
            "n_errors": sum(bool(r["function_error"]) for r in rs),
            "cold_p50_ms": float(np.median(cold_ms)),
            "cold_p50_ci95_lo": lo, "cold_p50_ci95_hi": hi,
            "cold_p95_ms": float(np.percentile(cold_ms, 95)),
            "init_p50_ms": float(np.median([r["init_ms"] for r in cold])),
            "cold_client_p50_ms": float(np.median([r["client_ms"] for r in cold])),
            "warm_p50_ms": float(np.median(warm_ms)),
            "warm_p95_ms": float(np.percentile(warm_ms, 95)),
            "warm_p99_ms": float(np.percentile(warm_ms, 99)),
            "max_memory_used_mb_max": max(r["max_memory_used_mb"] for r in rs if r["max_memory_used_mb"]),
            "billed_includes_init_share": float(np.mean([r["billed_includes_init"] for r in cold])),
            "mean_cost_cold_usd": cold_cost,
            "mean_cost_warm_usd": warm_cost,
            "meets_T": bool(np.median(cold_ms) <= TARGET["cold_p50_ms"]
                            and np.percentile(warm_ms, 95) <= TARGET["warm_p95_ms"]),
            "measured_cost_all_invocations_usd": float(sum(r["cost_usd"] for r in rs if r["cost_usd"])),
            "n_invocations_total": len(rs),
        }
        for c in COLD_SHARES:
            s[f"cost_per_1000_c{int(c * 100)}_usd"] = 1000 * ((1 - c) * warm_cost + c * cold_cost)
        summaries.append(s)

    sum_path = out_dir / "summary.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        w.writeheader()
        w.writerows(summaries)
    (out_dir / "summary.json").write_text(json.dumps(summaries, indent=2))
    print(f"wrote {inv_path} ({len(rows)} rows) and {sum_path}")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
