#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_trace_supplement.py — audit of the supplementary recorded-trace
experiment (exp11). Stdlib only; run in the directory holding:
  exp11_trace_replay.csv  (12 run rows, frozen graft schema)
  exp11_trace_beats.csv   (12000 per-beat rows)
Checks R1-R8; prints PASS/FAIL per check and a final verdict.
Frozen criteria reused: divergence = max_err > 100 m (paper Section 4.3).
"""
import csv, math, statistics, sys, collections

REPLAY = "exp11_trace_replay.csv"
BEATS = "exp11_trace_beats.csv"
DIV = 100.0  # frozen divergence criterion (m)

fails = []
def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
    if not cond:
        fails.append(name)

beats = list(csv.DictReader(open(BEATS)))
rep = {(r["pattern"], r["method"]): r for r in csv.DictReader(open(REPLAY))}
by = collections.defaultdict(list)
for r in beats:
    by[(r["trace"], r["method"])].append(r)

# R1: shape — 1000 beats per run, 3 arms per trace
arms = collections.defaultdict(set)
for (t, m) in by:
    arms[t].add(m)
check("R1 shape", len(beats) == 1000 * len(by)
      and all(len(g) == 1000 for g in by.values())
      and all(s == {"fixed20", "bsf", "v3"} for s in arms.values()),
      f"beats={len(beats)} runs={len(by)} traces={len(arms)}")

# R2: replay CSV metrics recompute exactly from beats
ok = True
for k, g in by.items():
    errs = [float(x["err"]) for x in g]
    tos = [int(x["timeout"]) for x in g]
    c = rep[k]
    ok &= (abs(max(errs) - float(c["max_err"])) < 1e-3
           and abs(math.sqrt(sum(e * e for e in errs) / len(errs)) - float(c["rmse"])) < 1e-3
           and abs(sum(tos) / len(tos) - float(c["timeout_rate"])) < 1e-3)
check("R2 replay-from-beats consistency", ok, "12/12 cells")

# R3: divergence verdicts under the frozen criterion — invariant: bsf 0/N
verdict = {k: max(float(x["err"]) for x in g) > DIV for k, g in by.items()}
n_div = lambda m: sum(v for (t, mm), v in verdict.items() if mm == m)
n_arm = lambda m: sum(1 for (t, mm) in verdict if mm == m)
div_s = "  ".join(f"{m} {n_div(m)}/{n_arm(m)}" for m in ("fixed20", "bsf", "v3"))
check("R3 verdicts (bsf invariant)", n_div("bsf") == 0 and n_div("fixed20") >= 1,
      div_s)

# R4: degenerate open-loop-hover mode — discard arms locked at u_hover from beat 0
seq = lambda k: [float(x["err"]) for x in by[k]]
d_bc = max(abs(a - b) for a, b in zip(seq(("traceB", "fixed20")), seq(("traceC", "fixed20"))))
d_cv3 = max(abs(a - b) for a, b in zip(seq(("traceB", "fixed20")), seq(("traceC", "v3"))))
to0 = all(by[k][0]["timeout"] == "1" for k in by)
check("R4 hover-lock bit-identity", d_bc == 0.0 and d_cv3 == 0.0 and to0,
      f"max|diff| B-vs-C fixed20={d_bc}, C fixed20-vs-v3={d_cv3}, timeout@beat0 all={to0}")

# R5: traceA solve-time contrast on the SAME budget sequence (doom-loop link ii)
med = lambda k: statistics.median(float(x["solve_ms"]) for x in by[k])
f20, bsfA = med(("traceA", "fixed20")), med(("traceA", "bsf"))
check("R5 traceA solve-time contrast", f20 > 1.5 * bsfA,
      f"fixed20 {f20:.1f} ms vs bsf {bsfA:.1f} ms = {f20/bsfA:.2f}x")

# R6: bsf tracks with zero completed solves (traceC: 1000/1000 timeouts)
g = by[("traceC", "bsf")]
rmse_c = math.sqrt(sum(float(x["err"])**2 for x in g) / len(g))
check("R6 bsf zero-completion tracking",
      sum(int(x["timeout"]) for x in g) == 1000 and rmse_c < 0.5,
      f"traceC timeouts=1000/1000, rmse={rmse_c:.4f} m")

# R7: v3 gear occupancy — L gear >= 0.99 on every trace (M1 consistency)
occ = {tr: sum(1 for x in by[(tr, "v3")] if x["gear"] == "L") / 1000
       for tr in ("traceA", "traceB", "traceC", "traceD")}
check("R7 v3 L-gear occupancy", all(v >= 0.99 for v in occ.values()),
      " ".join(f"{k[5:]}={v:.3f}" for k, v in sorted(occ.items())))

# R8: per-cell budget mean from beats matches replay CSV
ok = all(abs(statistics.fmean(float(x["budget_ms"]) for x in g)
             - float(rep[k]["budget_mean"])) < 0.2 for k, g in by.items())
means = {t: statistics.fmean(float(x["budget_ms"]) for x in by[(t, "bsf")])
         for t in ("traceA", "traceB", "traceC", "traceD")}
check("R8 budget means", ok, " ".join(f"{k[5:]}={v:.1f}ms" for k, v in sorted(means.items())))

print("\n" + ("ALL CHECKS PASS" if not fails else "FAILURES: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
