#!/usr/bin/env python3
"""exp08 burst-length scan (amendment i.9). Reuses exp07's frozen run_one/task_ref/
calibrate via import; only the burst generator is parameterized (blen sweep).
Design note: for a fixed seed the rng stream is identical across blen, so burst
ONSETS are matched by construction and only scarcity DURATION varies (dose-response).
Divergence criterion (i.7b): max_err > 100. mm fixed to 0.0. Seeds 330-344."""
import os, sys, time, argparse
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/injection"))
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/experiments/exp07_mujoco_graft"))
import numpy as np
import run_graft as rg

HDR = "task,method,blen,seed,budget_mean,rmse,max_err,e95,timeout_rate,iter_mean,time_q50,gearL,gearM,gearH,calib_ms,budget_scale,safety_rate"
BLENS = [5, 10, 15, 20, 30]
METHODS = ["v3", "fixed20"]
TASKS = ["hover", "step", "circle", "fig8"]

def gen_burst_len(n, seed, blen, base=70.0, low=15.0, p_start=0.0067):
    rng = np.random.default_rng(seed + 77777)  # same stream as exp07 gen_burst
    b = np.full(n, base)
    t = 0
    while t < n:
        if rng.random() < p_start:
            b[t:t+blen] = low; t += blen
        else:
            t += 1
    return b

def run_single(tj, blen, seed, m, out):
    if not (out and os.path.exists(out)):
        with open(out, "w") as f:
            f.write(HDR + "\n")
    cal = rg.calibrate()
    scale = cal / rg.CALIB_REF
    budgets = gen_burst_len(int(rg.TOTAL / rg.DT), seed, blen) * rg.KAPPA * scale
    e, to, it, ms, gf, sr = rg.run_one(tj, seed, m, budgets, 0.0)
    row = [tj, m, str(blen), str(seed), f"{budgets.mean():.1f}",
           f"{np.sqrt((e**2).mean()):.4f}", f"{e.max():.4f}",
           f"{np.quantile(e, 0.95):.4f}", f"{to.mean():.4f}",
           f"{it.mean():.1f}", f"{np.quantile(ms, 0.5):.1f}",
           f"{gf.get('L', 0):.3f}", f"{gf.get('M', 0):.3f}", f"{gf.get('H', 0):.3f}",
           f"{cal:.1f}", f"{scale:.3f}", f"{sr:.4f}"]
    with open(out, "a") as f:
        f.write(",".join(map(str, row)) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", nargs=4, metavar=("TASK", "BLEN", "SEED", "METHOD"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.single:
        run_single(a.single[0], int(a.single[1]), int(a.single[2]), a.single[3], a.out)
        return
    ap.error("exp08 runs via --single only; drive_scan.py is the batch driver")

if __name__ == "__main__":
    main()
