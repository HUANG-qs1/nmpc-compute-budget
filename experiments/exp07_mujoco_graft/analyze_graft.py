#!/usr/bin/env python3
"""exp07 module-4 analyzer skeleton: audit + divergence table + verdicts P1/P2/P3.

Pre-registration anchors (preregistration_v1_1.md, amendment i.7):
  (i.7b) divergence := max_err > 100   [frozen threshold]
  P1  recovery window: v3 circle/fig8 under periodic|burst divergence <= 20%
  P2  mechanism: median iter_mean(diverged v3) >= 5x median iter_mean(survivor v3);
      budget_mean reported as covariate (no systematic gap expected)
  P3  envelope order: div(v3) < div(fixed20) <= div(reactive)

Discipline:
  * stdlib only (cbmpc env has no pandas)
  * all statistics over the FULL seed set present in the CSV; no filtering beyond
    the pre-registered cell definitions (no cherry-picking)
  * on a partial/fixture CSV the verdicts are plumbing checks, NOT results
"""
import csv, math, statistics, sys
from collections import Counter, defaultdict

DIVERGE_MAX_ERR = 100.0  # (i.7b), frozen
NUM_FIELDS = ["mm", "budget_mean", "rmse", "max_err", "e95", "timeout_rate",
              "iter_mean", "time_q50", "gearL", "gearM", "gearH",
              "calib_ms", "budget_scale", "safety_rate"]

def load(path):
    rows = []
    with open(path, newline="") as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            rec = {"task": r["task"], "method": r["method"], "pattern": r["pattern"],
                   "seed": int(r["seed"]), "line": ln}
            for k in NUM_FIELDS:
                v = (r.get(k) or "").strip()
                rec[k] = float(v) if v else math.nan
            rec["diverged"] = rec["max_err"] > DIVERGE_MAX_ERR  # nan -> False; flagged in audit
            rows.append(rec)
    return rows

def audit(rows):
    print("== audit ==")
    print("  rows=%d" % len(rows))
    seeds = sorted({r["seed"] for r in rows})
    print("  seeds(%d): %s" % (len(seeds), seeds))
    for dim in ("method", "task", "pattern"):
        c = Counter(r[dim] for r in rows)
        print("  %s: %s" % (dim, dict(sorted(c.items()))))
    nan_rows = [r["line"] for r in rows if any(math.isnan(r[k]) for k in NUM_FIELDS)]
    print("  rows with empty numeric fields: %s" % (nan_rows if nan_rows else "none"))
    seen = Counter((r["task"], r["method"], r["pattern"], r["seed"], r["mm"]) for r in rows)
    dupes = [k for k, v in seen.items() if v > 1]
    print("  duplicate cells: %s" % (dupes if dupes else "none"))
    full = len(seeds) >= 15 and {"random", "periodic", "burst"} <= {r["pattern"] for r in rows}
    if not full:
        print("  !! partial/fixture CSV - verdicts below are plumbing checks, NOT results !!")

def divergence_table(rows):
    print("\n== divergence (max_err>100) by task/pattern/method ==")
    cells = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r["task"], r["pattern"], r["method"])
        cells[k][1] += 1
        cells[k][0] += 1 if r["diverged"] else 0
    for k in sorted(cells):
        d, n = cells[k]
        print("  %-6s %-9s %-8s div=%3d/%3d (%5.1f%%)" % (k[0], k[1], k[2], d, n, 100.0 * d / n))

def _div_rate(rows, method):
    sel = [r for r in rows if r["method"] == method]
    if not sel:
        return None
    return sum(1 for r in sel if r["diverged"]) / len(sel), len(sel)

def verdict_p1(rows):
    sel = [r for r in rows if r["method"] == "v3" and r["task"] in ("circle", "fig8")
           and r["pattern"] in ("periodic", "burst")]
    if not sel:
        return "P1: no v3 circle/fig8 @periodic|burst rows in this CSV"
    rate = sum(1 for r in sel if r["diverged"]) / len(sel)
    return ("P1 recovery-window: v3 circle/fig8 @periodic|burst div=%.1f%% "
            "(threshold <=20%%) -> %s  [n=%d]"
            % (100 * rate, "PASS" if rate <= 0.20 else "FAIL", len(sel)))

def verdict_p2(rows):
    div = [r for r in rows if r["method"] == "v3" and r["diverged"]]
    surv = [r for r in rows if r["method"] == "v3" and not r["diverged"]]
    if not div or not surv:
        return "P2: need both diverged and surviving v3 runs"
    it_d = statistics.median(r["iter_mean"] for r in div)
    it_s = statistics.median(r["iter_mean"] for r in surv)
    b_d = statistics.median(r["budget_mean"] for r in div)
    b_s = statistics.median(r["budget_mean"] for r in surv)
    ratio = it_d / it_s if it_s else math.inf
    return ("P2 doom-loop mechanism: iter_mean div=%.1f vs surv=%.1f (x%.1f, need >=5x) -> %s; "
            "budget_mean div=%.1fms vs surv=%.1fms (covariate)  [n=%d/%d]"
            % (it_d, it_s, ratio, "PASS" if ratio >= 5.0 else "FAIL", b_d, b_s, len(div), len(surv)))

def verdict_p3(rows):
    rates = {m: _div_rate(rows, m) for m in ("v3", "fixed20", "reactive")}
    if any(v is None for v in rates.values()):
        return "P3: missing method(s)"
    (v3r, n1), (f20r, n2), (rer, n3) = rates["v3"], rates["fixed20"], rates["reactive"]
    ok = v3r < f20r <= rer
    return ("P3 envelope order: v3=%.1f%% (n=%d) < fixed20=%.1f%% (n=%d) <= reactive=%.1f%% (n=%d) -> %s"
            % (100 * v3r, n1, 100 * f20r, n2, 100 * rer, n3, "PASS" if ok else "FAIL"))

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fixture_srv1.csv"
    rows = load(path)
    audit(rows)
    divergence_table(rows)
    print("\n== pre-registered verdicts ==")
    print("  " + verdict_p1(rows))
    print("  " + verdict_p2(rows))
    print("  " + verdict_p3(rows))

if __name__ == "__main__":
    main()
