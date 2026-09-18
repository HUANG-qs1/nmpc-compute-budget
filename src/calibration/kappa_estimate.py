# -*- coding: utf-8 -*-
"""kappa_estimate.py - D09: 可调度性先验 κ 初版
κ = cond(H_V) * B̄/Ts
H_V: 值函数(最优代价)对状态的 Hessian, 对角二阶差分估计
经验指标, 不宣称普适 (开题 3.3)
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/solver"))
import numpy as np
import casadi as ca
import nmpc_casadi as sc  # noqa (确保同源)

def optimal_cost(state, ref_segment, N=10, dt=0.1, tol=1e-4):
    """复刻 mpc_no_tube 的问题, 但返回最优值函数值"""
    x, y, theta = state
    U = ca.MX.sym('U', 2*N); v = U[0::2]; o = U[1::2]
    X = [x, y, theta]; obj = 0
    for k in range(N):
        xn = X[0]+v[k]*ca.cos(X[2])*dt; yn = X[1]+v[k]*ca.sin(X[2])*dt; tn = X[2]+o[k]*dt
        X = [xn, yn, tn]
        obj += (X[0]-ref_segment[k,0])**2 + (X[1]-ref_segment[k,1])**2 + 0.01*v[k]**2 + 0.01*o[k]**2
    g = [X[0]-x, X[1]-y, X[2]-theta]
    solver = ca.nlpsol('s','ipopt',{'x':U,'f':obj,'g':ca.vertcat(*g)},
                       {'print_time':False,'ipopt':{'print_level':0,'tol':tol}})
    res = solver(x0=[0.5,0.0]*N, lbx=[-1.0]*(2*N), ubx=[1.0]*(2*N), lbg=0, ubg=0)
    return float(res['f'])

def circle_path(radius=2.0, n=300):
    a = np.linspace(0, 2*np.pi, n); return np.stack([radius*np.cos(a), radius*np.sin(a)], 1)

def kappa_at(state, seg, h=1e-3, N=10):
    """对角 Hessian 条件数估计: d2V/dxi^2 的二阶中心差分"""
    V0 = optimal_cost(state, seg, N=N)
    diag = []
    for i in range(3):
        sp, sm = list(state), list(state)
        sp[i] += h; sm[i] -= h
        diag.append((optimal_cost(sp, seg, N=N) - 2*V0 + optimal_cost(sm, seg, N=N)) / h**2)
    diag = np.abs(np.array(diag))
    cond = diag.max() / max(diag.min(), 1e-12)
    return cond, diag

if __name__ == "__main__":
    ref = circle_path()
    Ts, B_bar = 0.1, 40.0   # 采样周期(s), 名义预算(ms)
    print("idx, cond(H_V), kappa")
    for idx in [60, 120, 180, 240]:
        state = [ref[idx,0]-0.05, ref[idx,1]+0.05, 0.3]
        seg = ref[np.clip(idx+np.arange(10), 0, len(ref)-1)]
        cond, diag = kappa_at(state, seg)
        kappa = cond * (B_bar/1000.0) / Ts
        print(f"{idx:4d}  cond={cond:10.2f}  kappa={kappa:8.3f}  diag={np.round(diag,2)}")
