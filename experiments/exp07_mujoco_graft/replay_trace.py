#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replay_trace.py - replay recorded real-scheduler budget traces through the
frozen exp07 closed loop (supplementary trace experiment; circle task,
nominal mismatch arm, initial condition seed 230 paired with frozen cells).

Arm parity with the frozen pipeline (run_graft.py):
- same plant, solver, DT/TOTAL/TOL, attitude safety supervisor, timeout rule
- same budget mapping: budgets_ms = units * KAPPA * scale,
  scale = calibrate()/CALIB_REF recomputed per run (as frozen runs do)
- same hard deadline: cap_s = max(budgets)/1000 per run
- same metrics and CSV columns as the frozen graft CSVs
- arms: fixed20 (frozen logic), v3 (frozen ComputeBudgeter), bsf via the
  server-native quad_mpc(partial=True) - the SAME function body the frozen
  exp10 bsf runs used (interrupted solver returns its current iterate;
  non-finite iterate falls back to u_hover; timeout still judged by wall
  clock, so bsf and fixed20 differ only in what happens on a timeout step)

This experiment is NOT part of the preregistered 2760-run set; it is an
illustrative supplement. The budget sequences come from OS scheduler
measurements (record_trace.py), not from a seeded random model.

Run in ~/compute-budget-mpc/experiments/exp07_mujoco_graft/ :
  python3 replay_trace.py traceA.csv traceB.csv traceC.csv traceD.csv
Sequential, ~30-50 min for 4 traces x 3 arms. Outputs:
  exp11_trace_replay.csv  (one row per run, frozen graft schema)
  exp11_trace_beats.csv   (per-beat log for figures)
"""
import os
import sys
import time
import argparse

import numpy as np

import quad_nmpc as qn
from quad_nmpc import ComputeBudgeter
from plant import QuadPlant
from run_graft import (task_ref, quat_to_rpy, unsafe, recovery_u, calibrate,
                       DT, TOTAL, TOL, KAPPA, CALIB_REF, HDR)

import inspect as _inspect
assert "partial" in _inspect.signature(qn.quad_mpc).parameters, \
    "requires the exp10-capable server quad_nmpc.py (quad_mpc partial kwarg)"

SEED = 230          # paired with the frozen circle cells (seeds 230-244)
TASK = "circle"
MM = 0.0            # nominal arm
TRIM = 25           # drop 25 beats at each end of each trace
STEPS = int(TOTAL / DT)

def run_one_trace(method, budgets, beats_log, trace_name):
    """Isomorphic to run_graft.run_one for TASK circle / mm 0.0, plus bsf arm."""
    cap_s = float(np.max(budgets)) / 1000.0  # hard deadline = run budget max
    plant = QuadPlant(mm=MM, dt=0.01)
    plant.reset(pos=(0, 0, 1.0), seed=SEED)
    plant.data.act[:] = [plant.mass * 9.81, 0, 0, 0]
    bd = ComputeBudgeter(dwell=1, use_freeze=False, online=True) if method == "v3" else None
    errs, timeouts, its, tms, gears = [], [], [], [], []
    prev_u = qn.U_HOVER.copy()
    safety_n = 0
    for t in range(STEPS):
        if bd:
            N = bd.decide(budgets[t])[0]
        else:
            N = 20
        seg = task_ref(TASK, (t + np.arange(N + 1)) * DT)
        s = plant.state()
        x12 = np.concatenate([s[0:3], s[7:10], quat_to_rpy(s[3:7]), s[10:13]])
        t0 = time.perf_counter()
        u = qn.quad_mpc(x12, seg, N=N, dt=DT, tol=TOL, cap_s=cap_s,
                        partial=(method == "bsf"))
        ms = (time.perf_counter() - t0) * 1000
        to = ms > budgets[t] or not qn.LAST_STATS["success"]
        if to and method != "bsf":
            u = prev_u  # discard policy (frozen); bsf applies late/partial u
        timeouts.append(1 if to else 0)
        it = qn.LAST_STATS["iter_count"]
        prev_u = u.copy()
        if bd:
            bd.update_timing(ms, timeouts[-1])
            gears.append(bd.gear)
        else:
            gears.append("")
        for _ in range(10):  # method-blind attitude safety supervisor (frozen)
            st = plant.state()
            if unsafe(st):
                plant.step(recovery_u(st, plant.mass))
                safety_n += 1
            else:
                plant.step(u)
        err = float(np.linalg.norm(plant.state()[0:3] - task_ref(TASK, t * DT)[0]))
        errs.append(err)
        its.append(it)
        tms.append(ms)
        beats_log.append((trace_name, method, t, f"{budgets[t]:.1f}",
                          f"{ms:.1f}", timeouts[-1], it,
                          bd.gear if bd else "", f"{err:.4f}"))
        if t % 100 == 0:
            print(f"  [{trace_name}/{method}] beat {t}/{STEPS} "
                  f"ms_last={ms:.0f} to={sum(timeouts)}", flush=True)
    gear_frac = {g: gears.count(g) / len(gears) for g in "LMH"} if bd else {}
    return (np.array(errs), np.array(timeouts), np.array(its),
            np.array(tms), gear_frac, safety_n / (STEPS * 10))


def load_units(path):
    units = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("beat"):
                continue
            p = line.strip().split(",")
            if len(p) >= 5:
                units.append(float(p[4]))
    u = np.array(units, float)
    assert u.size >= STEPS + 2 * TRIM, f"{path}: only {u.size} beats recorded"
    u = u[TRIM:TRIM + STEPS]
    assert np.all(np.isfinite(u)), f"{path}: non-finite units"
    assert (u > 0).all() and (u <= 74.0).all(), \
        f"{path}: units out of sane range [{u.min():.2f}, {u.max():.2f}]"
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traces", nargs="+", help="trace CSVs from record_trace.py")
    ap.add_argument("--out", default="exp11_trace_replay.csv")
    ap.add_argument("--beats-out", default="exp11_trace_beats.csv")
    a = ap.parse_args()

    methods = ["fixed20", "bsf", "v3"]
    need_hdr = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
    fout = open(a.out, "a")
    if need_hdr:
        fout.write(HDR + "\n")
    need_bhdr = not os.path.exists(a.beats_out) or os.path.getsize(a.beats_out) == 0
    bf = open(a.beats_out, "a")
    if need_bhdr:
        bf.write("trace,method,beat,budget_ms,solve_ms,timeout,iter,gear,err\n")

    t_all = time.time()
    for tr in a.traces:
        name = os.path.splitext(os.path.basename(tr))[0]
        units = load_units(tr)
        for m in methods:
            cal = calibrate()
            scale = cal / CALIB_REF
            budgets = units * KAPPA * scale
            print(f"[{name}/{m}] budget_mean={budgets.mean():.1f}ms "
                  f"cal={cal:.1f} scale={scale:.3f}", flush=True)
            beats_log = []
            t0 = time.time()
            e, to, it, ms, gf, sr = run_one_trace(m, budgets, beats_log, name)
            row = [TASK, m, name, SEED, f"{MM:.1f}", f"{budgets.mean():.1f}",
                   f"{np.sqrt((e ** 2).mean()):.4f}", f"{e.max():.4f}",
                   f"{np.quantile(e, 0.95):.4f}", f"{to.mean():.4f}",
                   f"{it.mean():.1f}", f"{np.quantile(ms, 0.5):.1f}",
                   f"{gf.get('L', 0):.3f}", f"{gf.get('M', 0):.3f}", f"{gf.get('H', 0):.3f}",
                   f"{cal:.1f}", f"{scale:.3f}", f"{sr:.4f}"]
            fout.write(",".join(map(str, row)) + "\n")
            fout.flush()
            for b in beats_log:
                bf.write(",".join(map(str, b)) + "\n")
            bf.flush()
            el = (time.time() - t0) / 60
            print(f"[{name}/{m}] done in {el:.1f} min: max_err={e.max():.3f} "
                  f"rmse={np.sqrt((e ** 2).mean()):.4f} to_rate={to.mean():.3f} "
                  f"safety_rate={sr:.5f}", flush=True)
    fout.close()
    bf.close()
    print(f"ALL DONE in {(time.time() - t_all) / 60:.1f} min -> {a.out}, {a.beats_out}",
          flush=True)


if __name__ == "__main__":
    main()
