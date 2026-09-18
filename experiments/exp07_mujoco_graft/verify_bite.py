"""Bite check v2: with solve watchdog + per-100-beat heartbeat."""
import numpy as np, time
import run_graft as rg
from run_graft import run_one, make_budgets, calibrate, KAPPA, CALIB_REF

_orig_run_one = rg.run_one  # heartbeat via wrapper not needed; just time it
cal = calibrate(); scale = cal / CALIB_REF
budgets = make_budgets("periodic", 1000, 95) * KAPPA * scale
print(f"calib={cal:.1f} scale={scale:.3f} kappa={KAPPA} budget lo/hi = {budgets.min():.0f}/{budgets.max():.0f} ms", flush=True)
for m in ["fixed20", "v3"]:
    t0 = time.time()
    e, to, it, ms, gf, sr = run_one("circle", 95, m, budgets, 0.0)
    print(f"{m:8s} TO={to.mean():.4f} RMSE={np.sqrt((e**2).mean()):.4f} "
          f"gears={gf} safety={sr:.4f} ms_max={ms.max():.0f} wall={time.time()-t0:.0f}s", flush=True)
