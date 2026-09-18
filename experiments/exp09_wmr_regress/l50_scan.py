#!/usr/bin/env python3
# l50_scan.py -- exp09 cliff-localization verdict instrument (D49)
# descriptive, no PASS/FAIL gate; reads main + probe + scan CSVs
import sys, math
from statistics import median

DIV_MAX_ERR = 5.0          # D48 frozen
SEEDS = set(range(430, 445))
Z = 1.96
P_START = 0.0067
def duty_frac(blen):
    # self-consistent: draws shrink as bursts consume beats
    return P_START*blen/(1.0 + P_START*(blen - 1))
GRID_FIG8 = [40, 50, 60, 70, 80, 90, 110, 130]  # D49 frozen scan grid
NEED = ["traj","method","pattern","seed","max_err","iter_mean","timeout_rate"]

def load(path):
    rows = []
    with open(path) as f:
        hdr = f.readline().strip().split(",")
        for n in NEED:
            assert n in hdr, "missing column %s in %s" % (n, path)
        idx = {n: hdr.index(n) for n in hdr}
        has_blen = "blen" in idx
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = line.split(",")
            rows.append(dict(
                traj=c[idx["traj"]], method=c[idx["method"]], pattern=c[idx["pattern"]],
                blen=int(c[idx["blen"]]) if has_blen else 30,
                seed=int(c[idx["seed"]]),
                max_err=float(c[idx["max_err"]]),
                iter_mean=float(c[idx["iter_mean"]]),
                timeout_rate=float(c[idx["timeout_rate"]])))
    return rows

def wilson(k, n):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + Z*Z/n
    ctr = (p + Z*Z/(2.0*n)) / d
    half = (Z/d) * math.sqrt(p*(1.0-p)/n + Z*Z/(4.0*n*n))
    return (max(0.0, ctr-half), min(1.0, ctr+half))

def fmt_cell(k, n):
    lo, hi = wilson(k, n)
    return "%2d/%2d  %.3f  [%.3f, %.3f]" % (k, n, k/n if n else float("nan"), lo, hi)

def main(paths):
    rows = []
    for p in paths:
        rows.extend(load(p))
    # guards
    bad = [r for r in rows if r["seed"] not in SEEDS]
    if bad:
        raise AssertionError("seed outside 430-444 found: %d rows (e.g. seed %d)" % (len(bad), bad[0]["seed"]))
    seen = {}
    dups = 0
    for r in rows:
        key = (r["traj"], r["method"], r["pattern"], r["blen"], r["seed"])
        if key in seen:
            dups += 1
        seen[key] = r
    cells = {}
    for r in rows:
        cells.setdefault((r["traj"], r["method"], r["pattern"], r["blen"]), []).append(r)

    print("== l50_scan verdict (descriptive, no gate; D49 frozen method) ==")
    print("rows loaded: %d from %d files | duplicate keys: %d" % (len(rows), len(paths), dups))

    partial = []
    expected = [("fig8","fixed20","burst",b) for b in GRID_FIG8] + \
               [("circle","fixed20","burst",100), ("circle","v3","burst",100)]
    for key in expected:
        n = len(cells.get(key, []))
        if n < 15:
            partial.append("%s/%s/blen=%d: %d/15 seeds" % (key[0], key[1], key[3], n))
    for key in [("fig8","fixed20","burst",30), ("fig8","fixed20","burst",100),
                ("fig8","v3","burst",30), ("fig8","v3","burst",100)]:
        n = len(cells.get(key, []))
        if n < 15:
            partial.append("anchor %s/%s/blen=%d: %d/15 seeds" % (key[0], key[1], key[3], n))
    if partial:
        print("PARTIAL CSV -- plumbing checks, NOT results:")
        for s in partial:
            print("  missing: " + s)

    # fixed20 fig8/burst divergence series
    pts = []
    print("\nfixed20 fig8/burst divergence series (DIV: max_err > %.1f, D48):" % DIV_MAX_ERR)
    print("blen  duty%   k/n     rate   Wilson95        it_div  it_surv  TO_med")
    for b in sorted({b for (t,m,p,b) in cells if (t,m,p)==("fig8","fixed20","burst")}):
        rs = cells[("fig8","fixed20","burst",b)]
        dv = [r for r in rs if r["max_err"] > DIV_MAX_ERR]
        sv = [r for r in rs if r["max_err"] <= DIV_MAX_ERR]
        itd = median([r["iter_mean"] for r in dv]) if dv else float("nan")
        its = median([r["iter_mean"] for r in sv]) if sv else float("nan")
        tom = median([r["timeout_rate"] for r in rs])
        pts.append((b, len(dv), len(rs)))
        print("%4d  %5.1f   %s   %6.2f  %6.2f  %.3f" % (
            b, 100.0*duty_frac(b), fmt_cell(len(dv), len(rs)), itd, its, tom))

    # L50 by frozen piecewise-linear interpolation on rate
    print("\n-- L50 (piecewise-linear on rate, frozen D49) --")
    rates = [(b, k/n) for (b, k, n) in sorted(pts) if n > 0]
    crossings = []
    for i in range(len(rates)-1):
        b0, r0 = rates[i]; b1, r1 = rates[i+1]
        if r0 == 0.5:
            crossings.append((b0, b0, b0))
        if (r0-0.5)*(r1-0.5) < 0:
            est = b0 + (0.5-r0)*(b1-b0)/(r1-r0)
            crossings.append((b0, b1, est))
    if rates and rates[-1][1] == 0.5:
        crossings.append((rates[-1][0], rates[-1][0], rates[-1][0]))
    if crossings:
        for (b0, b1, est) in crossings:
            if b0 == b1:
                print("L50 hit exactly at blen=%d" % b0)
            else:
                print("L50 crossing in (%d, %d): L50 ~= %.1f beats" % (b0, b1, est))
    elif rates:
        if rates[-1][1] < 0.5:
            print("no crossing: L50 > %d beats (lower bound only, no extrapolation)%s" % (rates[-1][0],
                  "; series non-monotone, interpret with care" if any(rates[i-1][1] > rates[i][1] for i in range(1, len(rates))) else ""))
        else:
            print("no crossing: L50 <= %d beats (upper bound only)%s" % (rates[0][0],
                  "; series non-monotone, interpret with care" if any(rates[i-1][1] > rates[i][1] for i in range(1, len(rates))) else ""))
    # onset
    nz = [(b, k) for (b, k, n) in pts if k > 0 and n > 0]
    if nz:
        b0 = nz[0][0]
        prev = [b for (b, k, n) in pts if k == 0 and b < b0]
        lo = prev[-1] if prev else None
        print("onset: first divergence at blen=%d%s" % (b0,
              ", bracket (%d, %d]" % (lo, b0) if lo is not None else " (no zero point below)"))
    else:
        print("onset: no divergence observed in grid")
    # monotone check (E1)
    dips = []
    for i in range(1, len(pts)):
        if pts[i-1][1] - pts[i][1] >= 2:   # D49: +/-1 seed dip = statistical noise
            dips.append((pts[i-1][0], pts[i][0], pts[i-1][1], pts[i][1]))
    print("E1 monotone: %s" % ("holds (within +/-1 seed noise)" if not dips else
          "violations (k drops >= 2 seeds): " + "; ".join("blen %d->%d: %d->%d seeds" % d for d in dips)))

    # context: v3 fig8 known points
    print("\ncontext v3 fig8/burst:")
    for b in sorted({b for (t,m,p,b) in cells if (t,m,p)==("fig8","v3","burst")}):
        rs = cells[("fig8","v3","burst",b)]
        k = sum(1 for r in rs if r["max_err"] > DIV_MAX_ERR)
        print("  blen=%4d: %s" % (b, fmt_cell(k, len(rs))))

    # P4 task severity contrast at blen=100
    print("\n-- task severity (P4): burst @ blen=100 --")
    for t in ("circle", "fig8"):
        for m in ("fixed20", "v3"):
            rs = cells.get((t, m, "burst", 100), [])
            if rs:
                k = sum(1 for r in rs if r["max_err"] > DIV_MAX_ERR)
                tom = median([r["timeout_rate"] for r in rs])
                print("  %-6s %-7s %s   TO_med %.3f" % (t, m, fmt_cell(k, len(rs)), tom))
    print("\n(ends)")

if __name__ == "__main__":
    main(sys.argv[1:])
