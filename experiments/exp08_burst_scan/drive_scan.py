#!/usr/bin/env python3
"""exp08 batch driver: one subprocess per run, resume via CSV rows.
Usage: nohup setsid python drive_scan.py OUTCSV > LOG 2>&1 &"""
import subprocess, sys, os, time, itertools

SEEDS = list(range(330, 345))   # i.9 registered block, disjoint from exp07 (230-244)
BLENS = [5, 10, 15, 20, 30]
TASKS = ["hover", "step", "circle", "fig8"]
METHODS = ["v3", "fixed20"]
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    out = sys.argv[1]
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            next(f)
            for line in f:
                p = line.split(",")
                done.add((p[0], p[1], int(p[2]), int(p[3])))
    combos = [c for c in itertools.product(SEEDS, BLENS, TASKS, METHODS)
              if (c[2], c[3], c[1], c[0]) not in done]
    print(f"driver: {len(combos)} runs to go", flush=True)
    assert len(combos) <= 600
    t0 = time.time()
    for ci, (seed, blen, tj, m) in enumerate(combos):
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_scan.py"),
                            "--single", tj, str(blen), str(seed), m, "--out", out])
        el = time.time() - t0
        print(f"[{ci+1}/{len(combos)}] {tj} blen={blen} {m} seed={seed} rc={r.returncode} "
              f"elapsed={el/60:.1f}min eta={el/(ci+1)*(len(combos)-ci-1)/60:.1f}min", flush=True)
    print("DRIVER ALL DONE", flush=True)

if __name__ == "__main__":
    main()
