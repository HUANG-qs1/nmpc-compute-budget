import numpy as np, time
from plant import QuadPlant
import quad_nmpc as qn
from quad_nmpc import quad_mpc
from run_graft import task_ref, quat_to_rpy, DT
for N in [10, 15, 20]:
    for tj in ["circle", "fig8"]:
        plant = QuadPlant(mm=0.0, dt=0.01)
        plant.reset(pos=(0, 0, 1.0), seed=90)
        plant.data.act[:] = [plant.mass * 9.81, 0, 0, 0]
        its, mss = [], []
        for t in range(120):
            seg = task_ref(tj, (t + np.arange(N+1)) * DT)
            s = plant.state()
            x12 = np.concatenate([s[0:3], s[7:10], quat_to_rpy(s[3:7]), s[10:13]])
            t0 = time.perf_counter()
            u = quad_mpc(x12, seg, N=N, dt=DT, tol=1e-4)
            mss.append((time.perf_counter()-t0)*1000)
            its.append(qn.LAST_STATS["iter_count"])
            for _ in range(10):
                plant.step(u)
        print(f"Np{N:2d} {tj:6s} iter_med={np.median(its[10:]):.0f} iter_q90={np.quantile(its[10:],0.9):.0f} ms_q90={np.quantile(mss[10:],0.9):.1f}")
