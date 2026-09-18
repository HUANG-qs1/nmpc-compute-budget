#!/usr/bin/env python3
"""exp08 module-4 analyzer: audit + blen-scan divergence table + verdicts P4/P5/P6.

Pre-registration anchors (amendment i.9, 2026-09-11):
  P4 dose-cliff: v3 per-task divergence non-decreasing across blen {5,10,15,20,30};
     AND circle+fig8 pooled divergence at blen=15 >= 40%
  P5 boundary shift: for circle and fig8 separately, L50(v3) > L50(fixed20), where
     L50 = smallest blen with pooled divergence >= 50% (inf if never reached);
     AND for hover/step at blen=30: div(v3) < div(fixed20)
  P6 mechanism (refined): mean iter_mean of diverged v3 runs non-decreasing in blen
Divergence (i.7b): max_err > 100.  Discipline: stdlib only, full seed set,
partial CSV -> verdicts are plumbing checks, NOT results."""
import csv, math, statistics, sys
from collections import Counter, defaultdict

DIVERGE_MAX_ERR = 100.0
BLENS = [5, 10, 15, 20, 30]
TASKS = ["hover", "step", "circle", "fig8"]
METHODS = ["v3", "fixed20"]
NUM_FIELDS = ["budget_mean", "rmse", "max_err", "e95", "timeout_rate", "iter_mean",
              "time_q50", "gearL", "gearM", "gearH", "calib_ms", "budget_scale", "safety_rate"]

def load(path):
    rows = []
    with open(path, newline="") as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            rec = {"task": r["task"], "method": r["method"], "blen": int(r["blen"]),
                   "seed": int(r["seed"]), "line": ln}
            for k in NUM_FIELDS:
                v = (r.get(k) or "").strip()
                rec[k] = float(v) if v else math.nan
            rec["diverged"] = rec["max_err"] > DIVERGE_MAX_ERR
            rows.append(rec)
    return rows

def audit(rows):
    print("== audit ==")
    print("  rows=%d" % len(rows))
    seeds = sorted({r["seed"] for r in rows})
    print("  seeds(%d): %s" % (len(seeds), seeds))
    for dim in ("method", "task", "blen"):
        c = Counter(r[dim] for r in rows)
        print("  %s: %s" % (dim, dict(sorted(c.items()))))
    nan_rows = [r["line"] for r in rows if any(math.isnan(r[k]) for k in NUM_FIELDS)]
    print("  rows with empty numeric fields: %s" % (nan_rows if nan_rows else "none"))
    seen = Counter((r["task"], r["method"], r["blen"], r["seed"]) for r in rows)
    dupes = [k for k, v in seen.items() if v > 1]
    print("  duplicate cells: %s" % (dupes if dupes else "none"))
    full = len(seeds) >= 15 and set(BLENS) <= {r["blen"] for r in rows} and len(rows) >= 600
    if not full:
        print("  !! partial CSV - verdicts below are plumbing checks, NOT results !!")

def div_rate(rows, task, method, blen):
    sel = [r for r in rows if r["task"] == task and r["method"] == method and r["blen"] == blen]
    if not sel:
        return None, 0
    return sum(1 for r in sel if r["diverged"]) / len(sel), len(sel)

def scan_table(rows):
    print("\n== divergence rate by task/method/blen (n=15 seeds each) ==")
    print("  %-6s %-8s" % ("task", "method") + "".join("%8d" % b for b in BLENS))
    for task in TASKS:
        for method in METHODS:
            cells = []
            for b in BLENS:
                rate, n = div_rate(rows, task, method, b)
                cells.append("  %5.1f%%" % (100 * rate) if rate is not None else "     n/a")
            print("  %-6s %-8s" % (task, method) + "".join("%8s" % c for c in cells))

def l50(rows, task, method):
    for b in BLENS:
        rate, n = div_rate(rows, task, method, b)
        if rate is not None and rate >= 0.50:
            return b
    return math.inf

def verdict_p4(rows):
    ok_all, lines = True, []
    for task in TASKS:
        seq = [div_rate(rows, task, "v3", b)[0] for b in BLENS]
        mono = all(seq[i] <= seq[i + 1] + 1e-9 for i in range(len(seq) - 1))
        ok_all &= mono
        lines.append("    v3 %-6s div=[%s] %s" % (task, ", ".join("%.0f%%" % (100 * x) for x in seq),
                                                  "mono" if mono else "NOT monotone"))
    sel = [r for r in rows if r["method"] == "v3" and r["task"] in ("circle", "fig8") and r["blen"] == 15]
    agg = sum(1 for r in sel if r["diverged"]) / len(sel) if sel else math.nan
    ok_agg = agg >= 0.40
    head = "P4 dose-cliff: per-task monotone %s; circle+fig8 @blen=15 = %.1f%% (need >=40%%) %s -> %s" % (
        "OK" if ok_all else "VIOLATED", 100 * agg, "OK" if ok_agg else "BELOW",
        "PASS" if (ok_all and ok_agg) else "FAIL")
    return "\n".join([head] + lines)

def verdict_p5(rows):
    lines, ok = [], True
    for task in ("circle", "fig8"):
        lv, lf = l50(rows, task, "v3"), l50(rows, task, "fixed20")
        good = lv > lf
        ok &= good
        lines.append("    %-6s L50(v3)=%s > L50(fixed20)=%s -> %s" % (
            task, "inf" if math.isinf(lv) else lv, "inf" if math.isinf(lf) else lf,
            "OK" if good else "FAIL"))
    for task in ("hover", "step"):
        rv, _ = div_rate(rows, task, "v3", 30)
        rf, _ = div_rate(rows, task, "fixed20", 30)
        good = rv < rf
        ok &= good
        lines.append("    %-6s @blen=30: v3=%.1f%% < fixed20=%.1f%% -> %s" % (
            task, 100 * rv, 100 * rf, "OK" if good else "FAIL"))
    return "\n".join(["P5 boundary shift -> %s" % ("PASS" if ok else "FAIL")] + lines)

def verdict_p6(rows):
    means = []
    for b in BLENS:
        its = [r["iter_mean"] for r in rows
               if r["method"] == "v3" and r["blen"] == b and r["diverged"]]
        means.append(statistics.mean(its) if its else math.nan)
    valid = [(b, m) for b, m in zip(BLENS, means) if not math.isnan(m)]
    mono = all(valid[i][1] <= valid[i + 1][1] + 1e-9 for i in range(len(valid) - 1))
    seq = ", ".join("blen=%d:%.1f" % (b, m) for b, m in valid)
    return "P6 mechanism: diverged-v3 iter_mean by blen [%s] -> %s" % (seq, "PASS" if mono else "FAIL")

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "20260911_exp08_scan_srv.csv"
    rows = load(path)
    audit(rows)
    scan_table(rows)
    print("\n== pre-registered verdicts (i.9) ==")
    print(verdict_p4(rows))
    print(verdict_p5(rows))
    print(verdict_p6(rows))

if __name__ == "__main__":
    main()
