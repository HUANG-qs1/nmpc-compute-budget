"""Quad NMPC graft layer (amendment i; patched i.7a). Mirrors exp05 beat logic exactly:
- same DT=0.1 beat, same timeout rule (ms>budget or fail -> prev_u)
- ComputeBudgeter imported unchanged; P2 priors deliberately NOT recalibrated
- controller model always nominal (m=1.0); mismatch lives only in plant.
i.7a: per-run hard deadline via ipopt max_cpu_time = run budget maximum (cap_s, seconds).
Beat-level semantics unchanged: any solve that would finish within budget_eff (<= run max)
finishes identically; any solve over budget_eff times out and runner holds prev_u either way.
Only wall-clock differs. CpuTime aborts keep the cached solver (guesses re-seeded each beat);
all other failures still trigger circuit-breaker rebuild."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import sys, time
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/scheduler"))
import numpy as np
import casadi as ca
from compute_budgeter import ComputeBudgeter  # graft: unchanged

DT, TOL = 0.1, 1e-4
M_NOM, G = 1.0, 9.81
IXX, IYY, IZZ = 0.006, 0.006, 0.011
U_LO = np.array([0.0, -1.0, -1.0, -0.5])
U_HI = np.array([20.0, 1.0, 1.0, 0.5])
U_HOVER = np.array([M_NOM * G, 0.0, 0.0, 0.0])
LAST_STATS = {"success": True, "iter_count": 0}

def _dyn(x, u):
    r, p, y = x[6], x[7], x[8]
    cr, sr, cp, sp, cy, sy = ca.cos(r), ca.sin(r), ca.cos(p), ca.sin(p), ca.cos(y), ca.sin(y)
    R = ca.vertcat(
        ca.horzcat(cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr),
        ca.horzcat(sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr),
        ca.horzcat(-sp, cp*sr, cp*cr))
    acc = R @ ca.vertcat(0, 0, u[0]) / M_NOM - ca.vertcat(0, 0, G)
    return ca.vertcat(x[3:6], acc, x[9:12],
                      ca.vertcat(u[1]/IXX, u[2]/IYY, u[3]/IZZ))

def _rk4(x, u, dt, nsub=5):
    h = dt / nsub
    for _ in range(nsub):
        k1 = _dyn(x, u); k2 = _dyn(x + h/2*k1, u)
        k3 = _dyn(x + h/2*k2, u); k4 = _dyn(x + h*k3, u)
        x = x + h/6*(k1 + 2*k2 + 2*k3 + k4)
    return x

_SOLVERS = {}

def _build(N, cap_s=None):
    opti = ca.Opti()
    x = opti.variable(12, N+1); u = opti.variable(4, N)
    x0 = opti.parameter(12); ref = opti.parameter(3, N+1)
    Wp, Wv, Wa, Ww = 20.0, 1.0, 0.5, 0.05
    cost = 0
    for k in range(N+1):
        ep = x[0:3, k] - ref[:, k]
        cost += Wp*(ep.T @ ep) + Wv*(x[3:6, k].T @ x[3:6, k])
        cost += Wa*(x[6:9, k].T @ x[6:9, k]) + Ww*(x[9:12, k].T @ x[9:12, k])
    for k in range(N):
        du = u[:, k] - U_HOVER
        cost += 0.1*du[0]**2 + 1.0*(du[1]**2 + du[2]**2 + du[3]**2)
        opti.subject_to(x[:, k+1] == _rk4(x[:, k], u[:, k], DT))
    opti.subject_to(x[:, 0] == x0)
    opti.subject_to(opti.bounded(U_LO, u, U_HI))
    opti.minimize(cost)
    iopts = {"tol": TOL, "max_iter": 200, "print_level": 0, "sb": "yes"}
    if cap_s is not None:
        iopts["max_cpu_time"] = float(cap_s)
    opti.solver("ipopt", {"ipopt": iopts, "print_time": False})
    return opti, x, u, x0, ref

def quad_mpc(x12, ref_seg, N, dt=DT, tol=TOL, cap_s=None, partial=False):
    """Solve one beat. ref_seg: (N+1, 3) positions. Returns u (4,).
    cap_s: hard deadline seconds (i.7a); None = uncapped (calibration & tests)."""
    key = (N, cap_s)
    if key not in _SOLVERS:
        _SOLVERS[key] = _build(N, cap_s)
    opti, x, u, x0, ref = _SOLVERS[key]
    opti.set_value(x0, x12)
    rs = np.asarray(ref_seg, float)
    if rs.shape[0] < N+1:
        rs = np.vstack([rs, np.repeat(rs[-1:], N+1-rs.shape[0], axis=0)])
    opti.set_value(ref, rs[:N+1].T)
    opti.set_initial(u, np.repeat(U_HOVER[:, None], N, axis=1))
    xg = np.repeat(x12[:, None], N+1, axis=1)  # state guess: interp current->ref
    xg[0:3, :] = x12[0:3, None] + (rs[:N+1].T - x12[0:3, None]) * np.linspace(0, 1, N+1)
    opti.set_initial(x, xg)
    try:
        sol = opti.solve()
        out = np.asarray(sol.value(u)[:, 0])
        LAST_STATS["success"] = True
        LAST_STATS["iter_count"] = int(opti.stats().get("iter_count", 0))
    except Exception as exc:
        LAST_STATS["success"] = False
        rs_msg = ""
        try:
            st = opti.stats()
            LAST_STATS["iter_count"] = int(st.get("iter_count", 200))
            rs_msg = str(st.get("return_status", ""))
        except Exception:
            LAST_STATS["iter_count"] = 200
        out = U_HOVER.copy()
        if partial:  # exp10 bsf: CpuTime 中止时取未收敛迭代序列的首拍控制
            try:
                cand = np.asarray(opti.debug.value(u), float)[:, 0]
                if cand.shape == (4,) and np.all(np.isfinite(cand)):
                    out = cand
            except Exception:
                pass
        if "CpuTime" not in rs_msg and "CpuTime" not in str(exc):
            _SOLVERS.pop(key, None)  # genuine failure: rebuild; CpuTime abort keeps solver
    return out
