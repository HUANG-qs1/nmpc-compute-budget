"""Quad gear scan (amendment i.5): measure q90 solve ms for Np 10/15/20.
Exploration seeds 90-94 only. Closed-loop realistic states, circle+fig8.
Output: gear_scan_quad.csv + printed q90 table."""
import numpy as np, time, csv
from plant import QuadPlant
import quad_nmpc as qn
from quad_nmpc import quad_mpc
from run_graft import task_ref, quat_to_rpy, DT

SEEDS = [90, 91, 92, 93, 94]
GEARS = [10, 15, 20]
BEATS = 200
rows = []
for N in GEARS:
    for tj in ["circle", "fig8"]:
        for seed in SEEDS:
            plant = QuadPlant(mm=0.0, dt=0.01)
            plant.reset(pos=(0, 0, 1.0), seed=seed)
            plant.data.act[:] = [plant.mass * 9.81, 0, 0, 0]
            for t in range(BEATS):
                seg = task_ref(tj, (t + np.arange(N+1)) * DT)
                s = plant.state()
                x12 = np.concatenate([s[0:3], s[7:10], quat_to_rpy(s[3:7]), s[10:13]])
                t0 = time.perf_counter()
                u = quad_mpc(x12, seg, N=N, dt=DT, tol=1e-4)
                ms = (time.perf_counter()-t0)*1000
                if t >= 10:  # skip transient
                    rows.append((N, tj, seed, ms))
                for _ in range(10):
                    plant.step(u)
            print(f"N={N} {tj} seed={seed} done", flush=True)

with open("gear_scan_quad.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Np", "task", "seed", "ms"]); w.writerows(rows)
print("\nNp    n     q50     q90     q95")
for N in GEARS:
    v = np.array([r[3] for r in rows if r[0] == N])
    print(f"{N:3d} {len(v):5d} {np.median(v):7.1f} {np.quantile(v,0.9):7.1f} {np.quantile(v,0.95):7.1f}")
