# -*- coding: utf-8 -*-
"""run_regress.py - exp09: WMR 回归复测 runner (D48, v2 增 blen 参数)
预登记期望(先于数据, 2026-09-12):
  主批 blen=30(冻结, exp07 同构): fixed20 在 fig8/burst 下发散率明显高于 v3
  探针 blen=100(fig8/burst, v3+fixed20, 种子 430-444, 全分支覆盖, 无 PASS/FAIL 门):
    (a) fixed20 发散 v3 不发散 -> WMR 悬崖位于 30<blen<=100 且 v3 跨平台挽救成立
    (b) 皆不发散 -> 本时间尺度 WMR 无有限悬崖, H_max 实际无界 (lambda~0 活证据)
    (c) 皆发散 -> 悬崖存在且 v3 无法挽救 (概率低: v3 超时恒 0 的机制与 blen 无关)
设计(用户签字): 任务={circle(温和), fig8(攻击)}, 方法={v3, fixed20},
  场景={periodic, burst}, 种子 430-444, n=15/格, 主批 120 runs + 探针 30 runs
burst 生成器逐字节复刻 exp07 run_graft.py gen_burst (流 offset 77777);
  blen=30 为冻结默认值, 探针用 --blen 100, CSV 落 blen 列
circle 复刻 exp00 circle_path (radius=2.0, 逐拍角步进 2pi/299), 延展至 1000 拍
WMR 惯例: budgets * scale, CALIB_REF=25.0, 无 KAPPA; ComputeBudgeter 参数不动
用法:
  python3 run_regress.py --smoke --out SMOKE.csv           # seed=95, 8 组合自检
  python3 run_regress.py --seeds 430-444 --out OUT.csv     # 主批 120 runs (blen=30)
  python3 run_regress.py --seeds 430-444 --blen 100 --traj fig8 --pattern burst --out OUT.csv  # 探针 30 runs
  python3 run_regress.py --single fig8 burst 95 v3 --blen 100 --out OUT.csv
断点续跑: 已存在的 (traj,method,pattern,blen,seed) 组合自动跳过
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import sys, time, argparse
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/solver"))
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/injection"))
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/scheduler"))
import numpy as np
import nmpc_casadi as sc
from markov_seq import gen_pattern
from compute_budgeter import ComputeBudgeter

METHODS = ["v3", "fixed20"]
FIXED_N = {"fixed20": 20}
TRAJ_NAMES = ["circle", "fig8"]
PATTERNS = ["periodic", "burst"]
DT, TOTAL, TOL = 0.1, 100.0, 1e-4
CALIB_REF = 25.0  # WMR 归一化时间尺基准 (ms), 修订(e), 与 exp05/exp06 一致
OUTDIR = os.path.expanduser("~/compute-budget-mpc/experiments/exp09_wmr_regress")
HEADER = ("traj,method,pattern,blen,seed,budget_mean,rmse,max_err,e95,timeout_rate,"
          "iter_mean,time_q50,time_drift,gearL,gearM,gearH,calib_ms,budget_scale")

def circle_path(radius=2.0, n=1000):
    """exp00 circle_path 的 1000 拍延展: 逐拍角步进 2pi/299 (exp00 的 linspace 端点
    包含语义), 前 300 拍与 D01 基线逐点一致, 之后按同一步进续绕"""
    ang = 2 * np.pi * np.arange(n) / 299.0
    return np.stack([radius * np.cos(ang), radius * np.sin(ang)], axis=1)

TRAJS = {"circle": circle_path(), "fig8": sc.figure8_path()}

def gen_burst(n, seed, base=70.0, low=15.0, p_start=0.0067, blen=30):
    """逐字节复刻 exp07 run_graft.py 的 gen_burst; 默认 blen=30 为冻结值"""
    rng = np.random.default_rng(seed + 77777)
    b = np.full(n, base)
    t = 0
    while t < n:
        if rng.random() < p_start:
            b[t:t+blen] = low; t += blen
        else:
            t += 1
    return b

def make_budgets(pattern, steps, seed, blen=30):
    if pattern == "burst":
        return gen_burst(steps, seed, blen=blen)
    return gen_pattern(pattern, steps, seed)

def disturbance_seq(seed, steps, amp=1.0):
    """与 exp05/exp06 同一函数: 每 seed 独立 rng, 同种子跨方法跨场景配对"""
    rng = np.random.default_rng(seed)
    return amp * (-0.1 + 0.05 * rng.standard_normal(steps))

def warmup_solver():
    seg = TRAJS["fig8"][np.arange(15)]
    x0 = np.array([0.0, 0.0, 0.0])
    for _ in range(2):
        sc.mpc_no_tube(x0, seg, N=15, dt=DT, tol=TOL)

def calibrate():
    """run 级: 固定基准 Np15 求解3次取中位 (ms), 与 exp06 同基准"""
    seg = TRAJS["fig8"][np.arange(15)]
    x0 = np.array([0.0, 0.0, 0.0])
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        sc.mpc_no_tube(x0, seg, N=15, dt=DT, tol=TOL)
        ts.append((time.perf_counter() - t0) * 1000)
    return float(np.median(ts))

def run_one(ref, seed, method, budgets):
    robot = sc.RobotFree(0, 0, 0.0, DT)
    bd = ComputeBudgeter(dwell=1, use_freeze=False, online=True) if method == "v3" else None
    steps = int(TOTAL / DT)
    dseq = disturbance_seq(seed, steps)
    errs, timeouts, its, tms, gears = [], [], [], [], []
    prev_u = (0.0, 0.0)
    for t in range(steps):
        if bd:
            N = bd.decide(budgets[t])[0]
        else:
            N = FIXED_N[method]
        idx = min(t, len(ref) - 1)
        seg = ref[np.clip(idx + np.arange(N), 0, len(ref) - 1)]
        t0 = time.perf_counter()
        v, o = sc.mpc_no_tube(robot.state, seg, N=N, dt=DT, tol=TOL)
        ms = (time.perf_counter() - t0) * 1000
        if ms > budgets[t] or not sc.LAST_STATS["success"]:
            v, o = prev_u; timeouts.append(1)
        else:
            timeouts.append(0)
        prev_u = (v, o)
        if bd:
            bd.update_timing(ms, timeouts[-1]); gears.append(bd.gear)
        robot.step(v, o, [dseq[t], 0])
        errs.append(np.hypot(robot.state[0] - ref[idx, 0], robot.state[1] - ref[idx, 1]))
        its.append(sc.LAST_STATS["iter_count"]); tms.append(ms)
    gear_frac = {g: gears.count(g) / len(gears) for g in "LMH"} if gears else {}
    return (np.array(errs), np.array(timeouts), np.array(its), np.array(tms), gear_frac)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="430-444")
    ap.add_argument("--out", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--single", nargs=4, metavar=("TRAJ", "PATTERN", "SEED", "METHOD"),
                    default=None)
    ap.add_argument("--blen", type=int, default=30)  # 30=冻结值(exp07 同构); 100=探针
    ap.add_argument("--traj", default=None)          # 限定单任务, 如 fig8
    ap.add_argument("--pattern", default=None)       # 限定单场景, 如 burst
    a = ap.parse_args()
    out = a.out or os.path.join(OUTDIR, time.strftime("%Y%m%d") + "_exp09_regress_v1.csv")
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            next(f)
            for line in f:
                c = line.strip().split(",")
                done.add((c[0], c[1], c[2], int(c[3]), int(c[4])))
    else:
        with open(out, "w") as f:
            f.write(HEADER + "\n")
    if a.single:
        combos = [(a.single[0], a.single[3], a.single[1], a.blen, int(a.single[2]))]
    else:
        if a.traj:
            assert a.traj in TRAJ_NAMES, "bad traj " + a.traj
        if a.pattern:
            assert a.pattern in PATTERNS, "bad pattern " + a.pattern
        lo, hi = a.seeds.split("-")
        seeds = list(range(int(lo), int(hi) + 1))
        if a.smoke:
            seeds = [95]
        trajs = [a.traj] if a.traj else TRAJ_NAMES
        pats = [a.pattern] if a.pattern else PATTERNS
        combos = [(tj, m, pp, a.blen, s) for s in seeds for tj in trajs
                  for pp in pats for m in METHODS]
        combos = [c for c in combos if c not in done]
    warmup_solver()
    t_start = time.time()
    if not combos:
        print("nothing to do (all combos present in " + out + ")")
    for i, (tj, m, pat, blen, seed) in enumerate(combos):
        calib = calibrate()
        scale = calib / CALIB_REF
        budgets = make_budgets(pat, int(TOTAL / DT), seed, blen=blen) * scale
        errs, tos, its, tms, gf = run_one(TRAJS[tj], seed, m, budgets)
        half = len(tms) // 2
        drift = float(np.median(tms[half:]) / max(np.median(tms[:half]), 1e-9))
        row = ("%s,%s,%s,%d,%d,%.1f,%.4f,%.4f,%.4f,%.4f,%.1f,%.1f,%.4f,"
               "%.3f,%.3f,%.3f,%.1f,%.3f\n") % (
            tj, m, pat, blen, seed, float(np.mean(budgets)),
            float(np.sqrt(np.mean(errs ** 2))), float(np.max(errs)),
            float(np.quantile(errs, 0.95)), float(np.mean(tos)),
            float(np.mean(its)), float(np.median(tms)), drift,
            gf.get("L", 0.0), gf.get("M", 0.0), gf.get("H", 0.0), calib, scale)
        with open(out, "a") as f:
            f.write(row)
        el = (time.time() - t_start) / 60
        eta = el / (i + 1) * (len(combos) - i - 1)
        print("[%d/%d] %s %s blen=%d %s seed=%d calib=%.1fms scale=%.2f elapsed=%.1fmin eta=%.1fmin"
              % (i + 1, len(combos), tj, pat, blen, m, seed, calib, scale, el, eta), flush=True)
    print("ALL DONE " + out)

if __name__ == "__main__":
    main()
