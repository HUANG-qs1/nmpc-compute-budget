"""Module-2 self-check: controller sanity, NO budget interference (N=15 fixed).
PASS criteria printed; do not proceed to module 3 if any FAIL."""
import numpy as np, time
from plant import QuadPlant
from quad_nmpc import quad_mpc, DT

ok = True
def run_beats(ref_fn, nbeats, mm=0.0, precharge=True):
    p = QuadPlant(mm=mm); p.reset(pos=(0, 0, 1.0))
    if precharge:
        p.data.act[:] = [p.mass * 9.81, 0, 0, 0]
    errs, zlog = [], []
    for t in range(nbeats):
        idx = np.arange(16) + t  # N=15 -> N+1 ref points
        ref = ref_fn(idx * DT)
        s = p.state()
        x12 = np.concatenate([s[0:3], s[7:10], np.zeros(3), s[10:13]])
        # extract roll/pitch/yaw from quat
        qw, qx, qy, qz = s[3:7]
        roll = np.arctan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy))
        pitch = np.arcsin(np.clip(2*(qw*qy-qz*qx), -1, 1))
        yaw = np.arctan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))
        x12[6:9] = [roll, pitch, yaw]
        u = quad_mpc(x12, ref, N=15)
        for _ in range(10):
            p.step(u)
        errs.append(np.linalg.norm(p.state()[0:3] - ref_fn(t*DT)[0]))
        zlog.append(p.state()[2])
    return np.array(errs), np.array(zlog)

t0 = time.time()
# 1) hover hold at (0,0,1): final err < 5cm
e1, _ = run_beats(lambda t: np.tile([0, 0, 1.0], (len(np.atleast_1d(t)), 1)) if np.ndim(t) else np.array([[0, 0, 1.0]]), 50)
r1 = e1[-1] < 0.05
print(f"hover : final_err={e1[-1]:.4f}m (<0.05) -> {'PASS' if r1 else 'FAIL'}")
ok &= r1
# 2) step z 1->1.5 at t=5s: z in [1.45,1.55] for last 20 beats
step_fn = lambda t: np.where(np.atleast_1d(t)[..., None] >= 5.0, 1.5, 1.0) * np.array([0, 0, 1.0]) + np.zeros((len(np.atleast_1d(t)), 3))
e2, z2 = run_beats(step_fn, 100)
r2 = np.all(np.abs(z2[-20:] - 1.5) < 0.05)
print(f"step  : z_final={z2[-1]:.4f}, last20 within 5cm -> {'PASS' if r2 else 'FAIL'}")
ok &= r2
# 3) circle r=1.5 z=1.5, period 20s: RMSE after 10s transient < 0.15m
def circ_fn(t):
    tt = np.atleast_1d(t)
    w = 2*np.pi/20.0
    return np.stack([1.5*np.cos(w*tt), 1.5*np.sin(w*tt), np.full_like(tt, 1.5)], 1)
e3, _ = run_beats(circ_fn, 400)
rmse3 = np.sqrt((e3[100:]**2).mean())
r3 = rmse3 < 0.15
print(f"circle: RMSE(post-transient)={rmse3:.4f}m (<0.15) -> {'PASS' if r3 else 'FAIL'}")
ok &= r3
print(f"elapsed={time.time()-t0:.0f}s")
print("MODULE2:", "ALL PASS" if ok else "FAIL - do not proceed")
