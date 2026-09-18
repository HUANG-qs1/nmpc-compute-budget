"""exp10 四旋翼驱动：fixed10 + bsf 两臂，seeds-outer，子进程隔离，时间盒。
断点续跑：已存在的 (task,pattern,seed,mm,method) 组合自动跳过。
用法: nohup python3 drive_exp10.py OUTCSV [HOURS] > LOG 2>&1 &"""
import subprocess, sys, os, time, itertools

SEEDS = list(range(230, 245))
PATTERNS = ["random", "periodic", "burst"]
TASKS = ["hover", "step", "circle", "fig8"]
MMS = [0.0, 0.2]
METHODS = ["fixed10", "bsf"]
HERE = os.path.dirname(os.path.abspath(__file__))


def load_done(out):
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            next(f)
            for line in f:
                p = line.split(",")
                done.add((p[0], p[2], int(p[3]), float(p[4]), p[1]))
    return done


def main():
    out = sys.argv[1]
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1e9
    done = load_done(out)
    combos = [c for c in itertools.product(SEEDS, PATTERNS, TASKS, MMS, METHODS)
              if (c[2], c[1], c[0], c[3], c[4]) not in done]
    print("driver: %d runs to go, time budget %.2f h" % (len(combos), hours), flush=True)
    t0 = time.time()
    for ci, (seed, pat, tj, mm, m) in enumerate(combos):
        if (time.time() - t0) / 3600.0 >= hours:
            print("DRIVER TIME BUDGET REACHED after %d runs; resume with same command"
                  % ci, flush=True)
            return
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_graft.py"),
                            "--single", tj, pat, str(seed), str(mm), m, "--out", out])
        el = time.time() - t0
        print("[%d/%d] %s %s mm=%.1f %s seed=%d rc=%d elapsed=%.1fmin eta=%.1fmin"
              % (ci + 1, len(combos), tj, pat, mm, m, seed, r.returncode,
                 el / 60, el / (ci + 1) * (len(combos) - ci - 1) / 60), flush=True)
    print("DRIVER ALL DONE", flush=True)


if __name__ == "__main__":
    main()
