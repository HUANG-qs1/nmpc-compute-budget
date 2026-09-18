"""i.7a self-verification (laptop, pre-server):
Test A (cap never fires): budget 500ms const, N=15 -> capped vs uncapped BITWISE identical.
Test B (cap fires every beat): budget 30ms, cap 0.030s -> timeout flags & held inputs identical;
capped wall-clock >=3x faster. Also exercises CpuTime-abort solver-reuse path (60 consecutive
aborts on one cached solver). Warmup beat per arm moves solver-build cost outside timing.
Expect: ALL PASS."""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/scheduler"))
import numpy as np
import quad_nmpc as qn

N = 15
def seg_circle(t):
    w = 2*np.pi/20.0
    ts = t*qn.DT + np.arange(N+1)*qn.DT
    return np.stack([1.5*np.cos(w*ts), 1.5*np.sin(w*ts), 1.5*np.ones_like(ts)], axis=1)

def run_arm(budgets, cap_s):
    x = np.zeros(12); x[2] = 1.0
    qn.quad_mpc(x, seg_circle(0), N=N, cap_s=cap_s)  # warmup: solver build outside timing
    prev = qn.U_HOVER.copy()
    us, tos, its = [], [], []
    t_wall = time.perf_counter()
    for t, b in enumerate(budgets):
        t0 = time.perf_counter()
        u = qn.quad_mpc(x, seg_circle(t), N=N, cap_s=cap_s)
        ms = (time.perf_counter()-t0)*1e3
        if ms > b or not qn.LAST_STATS["success"]:
            u = prev; tos.append(1)
        else:
            tos.append(0)
        prev = u.copy(); us.append(u.copy()); its.append(qn.LAST_STATS["iter_count"])
        x[0:3] = seg_circle(t)[0] + 0.2  # deterministic pseudo-state, identical across arms
    return np.array(us), np.array(tos), np.array(its), time.perf_counter()-t_wall

print("Test A: cap 0.5s vs uncapped, budget 500ms x 60 beats ...")
bA = np.full(60, 500.0)
u0, f0, i0, w0 = run_arm(bA, None)
u1, f1, i1, w1 = run_arm(bA, 0.5)
assert np.array_equal(f0, f1), f"A: timeout flags differ at {np.nonzero(f0 != f1)[0]}"
assert np.array_equal(u0, u1), "A: control sequence not bitwise identical"
assert f0.sum() == 0, f"A: timeouts at beats {np.nonzero(f0)[0]} (both arms)"
print(f"  A PASS  wall {w0:.1f}s vs {w1:.1f}s  timeouts {f0.sum()}/{f1.sum()}  bitwise identical")

print("Test B: cap 0.030s vs uncapped, budget 30ms x 60 beats (every beat aborts) ...")
bB = np.full(60, 30.0)
u0, f0, i0, w0 = run_arm(bB, None)
u1, f1, i1, w1 = run_arm(bB, 0.030)
assert np.array_equal(f0, f1), f"B: timeout flags differ at {np.nonzero(f0 != f1)[0]}"
assert f0.sum() == 60, f"B: expected all-timeout, got {f0.sum()}"
assert np.array_equal(u0, u1), "B: held-input sequence differs"
assert w1 < w0/3.0, f"B: speedup too small ({w0:.1f}s -> {w1:.1f}s)"
print(f"  B PASS  wall {w0:.1f}s -> {w1:.1f}s ({w0/max(w1,1e-9):.1f}x faster)  iter_med {np.median(i0):.0f} -> {np.median(i1):.0f}")
print("ALL PASS")
