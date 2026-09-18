"""Batch driver: one subprocess per run (process-level isolation).
Resume via CSV rows. Usage: nohup python drive_batch.py OUTCSV LOGPREFIX &"""
import subprocess, sys, os, time, itertools

SEEDS = list(range(230, 245))
PATTERNS = ["random", "periodic", "burst"]
TASKS = ["hover", "step", "circle", "fig8"]
MMS = [0.0, 0.2]
METHODS = ["v3", "reactive", "fixed20"]
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    out = sys.argv[1]
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            next(f)
            for line in f:
                p = line.split(",")
                done.add((p[0], p[2], int(p[3]), float(p[4]), p[1]))
    combos = [c for c in itertools.product(SEEDS, PATTERNS, TASKS, MMS, METHODS)
              if (c[2], c[1], c[0], c[3], c[4]) not in done]
    print(f"driver: {len(combos)} runs to go", flush=True)
    t0 = time.time()
    for ci, (seed, pat, tj, mm, m) in enumerate(combos):
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_graft.py"),
                            "--single", tj, pat, str(seed), str(mm), m, "--out", out])
        el = time.time() - t0
        print(f"[{ci+1}/{len(combos)}] {tj} {pat} mm={mm} {m} seed={seed} rc={r.returncode} "
              f"elapsed={el/60:.1f}min eta={el/(ci+1)*(len(combos)-ci-1)/60:.1f}min", flush=True)
    print("DRIVER ALL DONE", flush=True)

if __name__ == "__main__":
    main()
