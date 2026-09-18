#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verification computations for v5-revision (review M1 + F2).
M1: per-task gear occupancy of v3 (and all quad arms), exp07 graft CSV.
F2: attitude-supervisor trip rate (safety_rate) by arm x task, exp07+exp10 CSVs.
Formula: cell value = mean of run-level column over the cell; counts printed.
Inputs:
  exp07 graft: 20260909_exp07_graft_srv2.csv (1080 rows; v3/reactive/fixed20)
  exp10 quad : exp10_quad.csv (720 rows; fixed10/bsf)
"""
import csv, statistics as st
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base = ROOT + "/experiments/exp07_mujoco_graft/"
e07 = list(csv.DictReader(open(base + "20260909_exp07_graft_srv2.csv")))
e10 = list(csv.DictReader(open(base + "exp10_quad.csv")))
assert len(e07) == 1080 and len(e10) == 720, (len(e07), len(e10))
TASKS = ["hover", "step", "circle", "fig8"]

def cell(rows, method, task):
    return [r for r in rows if r["method"] == method and r["task"] == task]

print("=== M1: v3 gear occupancy (mean share per task, n runs) ===")
for t in TASKS:
    c = cell(e07, "v3", t)
    gL = st.mean(float(r["gearL"]) for r in c)
    gM = st.mean(float(r["gearM"]) for r in c)
    gH = st.mean(float(r["gearH"]) for r in c)
    med = st.median(float(r["gearL"]) for r in c)
    print(f"v3/{t}: n={len(c)}  gearL={gL:.3f} gearM={gM:.3f} gearH={gH:.3f} (median gearL={med:.3f})")
allv3 = [r for r in e07 if r["method"] == "v3"]
print(f"v3/all: n={len(allv3)} meanL={st.mean(float(r['gearL']) for r in allv3):.3f} "
      f"medianL={st.median(float(r['gearL']) for r in allv3):.3f}")

print("\n=== M1b: v3 gear occupancy by task x pattern ===")
for t in TASKS:
    for p in ("random", "periodic", "burst"):
        c = [r for r in e07 if r["method"] == "v3" and r["task"] == t and r["pattern"] == p]
        gL = st.mean(float(r["gearL"]) for r in c)
        gH = st.mean(float(r["gearH"]) for r in c)
        print(f"v3/{t}/{p}: n={len(c)} gearL={gL:.3f} gearH={gH:.3f}", end="   ")
    print()

print("\n=== M1c: survivor rmse medians (v3 vs fixed10), quad, for context ===")
for t in TASKS:
    v3s = [float(r["rmse"]) for r in cell(e07, "v3", t) if float(r["max_err"]) <= 100]
    f10s = [float(r["rmse"]) for r in cell(e10, "fixed10", t) if float(r["max_err"]) <= 100]
    print(f"{t}: v3 surv n={len(v3s)} med={st.median(v3s):.4f} | fixed10 surv n={len(f10s)} med={st.median(f10s):.4f}")

print("\n=== F2: supervisor trip rate (safety_rate) by arm x task ===")
for rows, name in ((e07, "exp07"), (e10, "exp10")):
    for m in sorted({r["method"] for r in rows}):
        line = f"{m:9s}"
        for t in TASKS:
            c = cell(rows, m, t)
            v = [float(r["safety_rate"]) for r in c]
            line += f" | {t} n={len(c)} mean={st.mean(v)*100:.2f}% max={max(v)*100:.1f}%"
        print(line)
print("\n=== F2 overall by arm ===")
for rows, name in ((e07, "exp07"), (e10, "exp10")):
    for m in sorted({r["method"] for r in rows}):
        v = [float(r["safety_rate"]) for r in rows if r["method"] == m]
        nz = sum(1 for x in v if x > 0)
        print(f"{m:9s} n={len(v)} mean={st.mean(v)*100:.3f}% median={st.median(v)*100:.3f}% max={max(v)*100:.2f}% runs_with_trips={nz}/{len(v)}")

# === M1d (added): upshift-episode precision gain on hover; survivor timeout rates v3 vs fixed10 ===
import statistics as st
v3h = [r for r in e07 if r["method"]=="v3" and r["task"]=="hover" and float(r["max_err"])<=100]
hi  = [float(r["rmse"]) for r in v3h if float(r["gearM"])>=0.03]
lo  = [float(r["rmse"]) for r in v3h if float(r["gearM"])<0.03]
print(f"v3 hover survivors: gearM>=3% n={len(hi)} med rmse={st.median(hi):.4f} | gearM<3% n={len(lo)} med rmse={st.median(lo):.4f}")
print("survivor timeout_rate medians by task (v3 vs fixed10):")
Q = e07 + e10
for t in ["hover","step","circle","fig8"]:
    for m in ["v3","fixed10"]:
        sv=[float(r["timeout_rate"]) for r in Q if r["method"]==m and r["task"]==t and float(r["max_err"])<=100]
        print(f"  {t:6s} {m:7s} surv n={len(sv):3d} TO med={st.median(sv):.3f}")

# === M1e (added): run-mean timeout rate per task, v3 vs fixed10 (n=90 each) ===
print("run-mean timeout_rate by task (v3 vs fixed10, n=90):")
for t in ["hover","step","circle","fig8"]:
    for m in ["v3","fixed10"]:
        rows=[r for r in Q if r["method"]==m and r["task"]==t]
        print(f"  {t:6s} {m:7s} TO mean={st.mean(float(r['timeout_rate']) for r in rows):.3f}")
