"""exp07 graft runner v2 (amendment i + i.5). Beat logic isomorphic to exp05.
v2 adds method-blind attitude safety supervisor (firmware-style):
  fires when |roll|>1.0 or |pitch|>1.0 rad or non-finite state;
  recovery = PD-to-level + 1.2x hover thrust; identical for all arms;
  interventions counted per substep -> safety_rate column.
Burst pattern frozen 2026-09-08: base 70ms, bursts 30 beats at 15ms, p=0.0067.
KAPPA=6.052, CALIB_REF=285.0 frozen per amendment i.5 (gear scan D41).
i.8 (D45): --dump NPZ on --single exports per-beat trajectory/timing for the
render pipeline. Default off; batch branch never dumps; numerics unchanged."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import sys, time, itertools, argparse
sys.path.insert(0, os.path.expanduser("~/compute-budget-mpc/src/injection"))
import numpy as np
from markov_seq import gen_pattern
from plant import QuadPlant
import quad_nmpc as qn
from quad_nmpc import quad_mpc, ComputeBudgeter

DT, TOTAL, TOL = 0.1, 100.0, 1e-4
HDR = "task,method,pattern,seed,mm,budget_mean,rmse,max_err,e95,timeout_rate,iter_mean,time_q50,gearL,gearM,gearH,calib_ms,budget_scale,safety_rate"
CALIB_REF = 285.0  # CALIB_REF_quad (i.5): far-state Np15 probe median, laptop 2026-09-08
KAPPA = 6.052      # q90_quad(Np15)/27.0 = 163.4/27.0, gear scan D41
METHODS = ["v3", "reactive", "fixed20"]
FIXED_N = {"fixed20": 20}
REACT_GEARS = [10, 15, 20]
TASKS = ["hover", "step", "circle", "fig8"]
PATTERNS = ["random", "periodic", "burst"]
MMS = [0.0, 0.2]
ATT_LIM = 1.0  # rad, safety supervisor threshold

def gen_burst(n, seed, base=70.0, low=15.0, p_start=0.0067, blen=30):
    rng = np.random.default_rng(seed + 77777)
    b = np.full(n, base)
    t = 0
    while t < n:
        if rng.random() < p_start:
            b[t:t+blen] = low; t += blen
        else:
            t += 1
    return b

def make_budgets(pattern, steps, seed):
    if pattern == "burst":
        return gen_burst(steps, seed)
    return gen_pattern(pattern, steps, seed)

def task_ref(task, tt):
    tt = np.atleast_1d(np.asarray(tt, float))
    if task == "hover":
        return np.tile([0.0, 0.0, 1.0], (len(tt), 1))
    if task == "step":
        return np.stack([np.zeros_like(tt), np.zeros_like(tt),
                         np.where(tt >= 5.0, 1.5, 1.0)], 1)
    if task == "circle":
        w = 2*np.pi/20.0
        return np.stack([1.5*np.cos(w*tt), 1.5*np.sin(w*tt),
                         np.full_like(tt, 1.5)], 1)
    if task == "fig8":
        w = 2*np.pi/25.0
        return np.stack([1.5*np.sin(w*tt), 1.5*np.sin(w*tt)*np.cos(w*tt),
                         np.full_like(tt, 1.5)], 1)
    raise ValueError(task)

def quat_to_rpy(q):
    qw, qx, qy, qz = q
    roll = np.arctan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy))
    pitch = np.arcsin(np.clip(2*(qw*qy-qz*qx), -1, 1))
    yaw = np.arctan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))
    return roll, pitch, yaw

def unsafe(s):
    if not np.all(np.isfinite(s)):
        return True
    r, p, _ = quat_to_rpy(s[3:7])
    return abs(r) > ATT_LIM or abs(p) > ATT_LIM

def recovery_u(s, mass):
    r, p, y = quat_to_rpy(s[3:7])
    wx, wy, wz = s[10:13]
    return np.array([mass*9.81*1.2,
                     -0.6*r - 0.2*wx, -0.6*p - 0.2*wy, -0.2*wz])

def calibrate():
    seg = task_ref("circle", np.arange(16) * DT)
    x12 = np.zeros(12)
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        quad_mpc(x12, seg, N=15, dt=DT, tol=TOL)
        ts.append((time.perf_counter()-t0)*1000)
    return float(np.median(ts))

HB = os.environ.get("GRAFT_HB", "1") == "1"

def run_one(task, seed, method, budgets, mm, dump=None, meta=None):
    CAP_S = float(np.max(budgets)) / 1000.0  # i.7a: hard deadline = run budget max; calibrate() stays uncapped
    plant = QuadPlant(mm=mm, dt=0.01)
    plant.reset(pos=(0, 0, 1.0), seed=seed)
    plant.data.act[:] = [plant.mass * 9.81, 0, 0, 0]
    bd = ComputeBudgeter(dwell=1, use_freeze=False, online=True) if method == "v3" else None
    react_i = 1
    steps = int(TOTAL / DT)
    errs, timeouts, its, tms, gears = [], [], [], [], []
    prev_u = qn.U_HOVER.copy()
    safety_n = 0
    x12_log, u_log, n_log, sbeat_log = [], [], [], []  # i.8 dump-only collectors
    for t in range(steps):
        if bd:
            N = bd.decide(budgets[t])[0]
        elif method == "reactive":
            N = REACT_GEARS[react_i]
        else:
            N = FIXED_N[method]
        seg = task_ref(task, (t + np.arange(N+1)) * DT)
        s = plant.state()
        x12 = np.concatenate([s[0:3], s[7:10], quat_to_rpy(s[3:7]), s[10:13]])
        if dump is not None:
            x12_log.append(x12.copy())
        t0 = time.perf_counter()
        u = quad_mpc(x12, seg, N=N, dt=DT, tol=TOL, cap_s=CAP_S)
        ms = (time.perf_counter()-t0)*1000
        if ms > budgets[t] or not qn.LAST_STATS["success"]:
            u = prev_u; timeouts.append(1)
        else:
            timeouts.append(0)
        prev_u = u.copy()
        if dump is not None:
            u_log.append(u.copy()); n_log.append(N)
        if bd:
            bd.update_timing(ms, timeouts[-1]); gears.append(bd.gear)
        elif method == "reactive":
            if timeouts[-1] == 1 and react_i > 0:
                react_i -= 1
            elif timeouts[-1] == 0 and ms < 0.6*budgets[t] and react_i < 2:
                react_i += 1
            gears.append("LMH"[react_i])
        s0 = safety_n
        for _ in range(10):
            st = plant.state()
            if unsafe(st):
                plant.step(recovery_u(st, plant.mass)); safety_n += 1
            else:
                plant.step(u)
        if dump is not None:
            sbeat_log.append(safety_n - s0)
        if HB and t % 100 == 0:
            print(f"  beat {t}/{steps} ms_last={ms:.0f} to={sum(timeouts)}", flush=True)
        errs.append(np.linalg.norm(plant.state()[0:3] - task_ref(task, t*DT)[0]))
        its.append(qn.LAST_STATS["iter_count"]); tms.append(ms)
    if dump is not None:  # i.8: trajectory/timing export for render pipeline
        if not dump.endswith(".npz"):
            dump += ".npz"
        md = meta or {}
        np.savez_compressed(dump, errs=np.array(errs), timeouts=np.array(timeouts),
                            its=np.array(its), tms=np.array(tms),
                            budgets=np.asarray(budgets, float),
                            x12=np.array(x12_log), u=np.array(u_log),
                            N=np.array(n_log), safety_beats=np.array(sbeat_log),
                            task=task, method=method, seed=seed, mm=mm,
                            calib_ms=md.get("calib_ms", float("nan")),
                            budget_scale=md.get("budget_scale", float("nan")),
                            pattern=md.get("pattern", ""))
    gear_frac = {g: gears.count(g)/len(gears) for g in "LMH"} if gears else {}
    return (np.array(errs), np.array(timeouts), np.array(its),
            np.array(tms), gear_frac, safety_n/(steps*10))

def parse_seeds(s):
    a, b = s.split("-"); return list(range(int(a), int(b)+1))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default=None, choices=PATTERNS)
    ap.add_argument("--seeds", default="230-244")
    ap.add_argument("--out", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--single", nargs=5, metavar=("TASK","PATTERN","SEED","MM","METHOD"))
    ap.add_argument("--dump", default=None, metavar="NPZ",
                    help="i.8: with --single, export per-beat trajectory/timing npz (default off)")
    a = ap.parse_args()
    if a.single:  # subprocess mode: exactly one run, process-level isolation
        tj, pat, seed, mm, m = a.single[0], a.single[1], int(a.single[2]), float(a.single[3]), a.single[4]
        out = a.out
        if not (out and os.path.exists(out)):
            with open(out, "w") as f: f.write(HDR + "\n")
        cal = calibrate()
        scale = cal / CALIB_REF
        budgets = make_budgets(pat, int(TOTAL/DT), seed) * KAPPA * scale
        e, to, it, ms, gf, sr = run_one(tj, seed, m, budgets, mm, dump=a.dump,
                                        meta={"calib_ms": cal, "budget_scale": scale, "pattern": pat})
        if a.dump:
            print(f"dumped -> {a.dump}", flush=True)
        row = [tj, m, pat, seed, f"{mm:.1f}", f"{budgets.mean():.1f}",
               f"{np.sqrt((e**2).mean()):.4f}", f"{e.max():.4f}",
               f"{np.quantile(e, 0.95):.4f}", f"{to.mean():.4f}",
               f"{it.mean():.1f}", f"{np.quantile(ms, 0.5):.1f}",
               f"{gf.get('L', 0):.3f}", f"{gf.get('M', 0):.3f}", f"{gf.get('H', 0):.3f}",
               f"{cal:.1f}", f"{scale:.3f}", f"{sr:.4f}"]
        with open(out, "a") as f:
            f.write(",".join(map(str, row)) + "\n")
        return
    patterns = [a.pattern] if a.pattern else PATTERNS
    seeds = parse_seeds(a.seeds)
    tasks, mms, methods = TASKS, MMS, METHODS
    if a.smoke:
        patterns, seeds, tasks, mms, methods = ["random"], [95], ["circle"], [0.0], ["v3", "fixed20"]
    out = a.out or time.strftime("%Y%m%d") + "_exp07_graft.csv"
    hdr = "task,method,pattern,seed,mm,budget_mean,rmse,max_err,e95,timeout_rate,iter_mean,time_q50,gearL,gearM,gearH,calib_ms,budget_scale,safety_rate"
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            next(f)
            for line in f:
                p = line.split(",")
                done.add((p[0], p[1], p[2], int(p[3]), float(p[4])))
        fout = open(out, "a")
    else:
        fout = open(out, "w"); fout.write(hdr + "\n")
    combos = [c for c in itertools.product(seeds, patterns, tasks, mms, methods)
              if (c[2], c[4], c[1], c[0], c[3]) not in done]
    steps = int(TOTAL / DT)
    t_start = time.time()
    for ci, (seed, pat, tj, mm, m) in enumerate(combos):
        cal = calibrate()
        scale = cal / CALIB_REF
        budgets = make_budgets(pat, steps, seed) * KAPPA * scale
        e, to, it, ms, gf, sr = run_one(tj, seed, m, budgets, mm)
        row = [tj, m, pat, seed, f"{mm:.1f}", f"{budgets.mean():.1f}",
               f"{np.sqrt((e**2).mean()):.4f}", f"{e.max():.4f}",
               f"{np.quantile(e, 0.95):.4f}", f"{to.mean():.4f}",
               f"{it.mean():.1f}", f"{np.quantile(ms, 0.5):.1f}",
               f"{gf.get('L', 0):.3f}", f"{gf.get('M', 0):.3f}", f"{gf.get('H', 0):.3f}",
               f"{cal:.1f}", f"{scale:.3f}", f"{sr:.4f}"]
        fout.write(",".join(map(str, row)) + "\n"); fout.flush()
        if ci % 5 == 0:
            el = time.time()-t_start
            print(f"[{ci+1}/{len(combos)}] {tj} {pat} mm={mm} {m} seed={seed} "
                  f"calib={cal:.1f}ms scale={scale:.2f} elapsed={el/60:.1f}min "
                  f"eta={el/(ci+1)*(len(combos)-ci-1)/60:.1f}min", flush=True)
    fout.close()
    print("ALL DONE", out)

if __name__ == "__main__":
    main()
