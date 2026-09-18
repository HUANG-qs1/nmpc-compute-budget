#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""record_trace.py - record a real-scheduler compute-availability trace.

Measures, on this machine, how much CPU time a single CPU-bound thread
(standing in for the NMPC solver) actually receives per control beat, while
N busy processes contend for the cores. The per-beat duty cycle
d_k = cpu_ms / wall_ms is a genuine artifact of the OS scheduler, not of a
seeded random model. Output units_k = 70 * d_k express availability in the
same normalized budget units as the frozen synthetic patterns (70 = base
level); the replay pipeline applies the identical KAPPA * scale mapping to
milliseconds, so duty 1.0 corresponds exactly to the frozen base budget.

Stdlib only. Writes one CSV. Run on the cloud server (same host as replay).

Usage:
  python3 record_trace.py --workers 5  --out traceA.csv
  python3 record_trace.py --workers 9  --out traceB.csv
  python3 record_trace.py --workers 15 --out traceC.csv
  python3 record_trace.py --workers 23 --out traceD.csv

Each run records --beats beats (default 1050 = 105 s at the 10 Hz beat);
the replay trims 25 beats at each end and uses the middle 1000.
Do NOT run anything else heavy on the server while recording.
"""
import argparse
import multiprocessing as mp
import os
import platform
import statistics
import time


def _busy(deadline):
    """Contending process: pure CPU busy loop until deadline.
    No shared synchronization state (vDSO time check only), so each worker
    truly saturates a core; a shared Event check would futex-serialize the
    workers and make them block instead of compete."""
    x = 0.0
    while time.time() < deadline:
        x += 1.0
        if x >= 1e6:
            x = 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, required=True,
                    help="number of contending busy processes")
    ap.add_argument("--beats", type=int, default=1050)
    ap.add_argument("--period", type=float, default=0.1,
                    help="beat length in seconds (control beat = 0.1 s)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    assert a.workers >= 1, "need at least 1 contending worker"
    assert a.beats >= 60, "record at least 60 beats"
    assert a.period > 0.01

    duration = a.beats * a.period
    deadline = time.time() + duration + 5.0  # workers self-exit after recording
    procs = [mp.Process(target=_busy, args=(deadline,), daemon=True)
             for _ in range(a.workers)]
    for p in procs:
        p.start()
    time.sleep(1.0)  # let contention reach steady state

    # Recorder: spin in the main thread like a solver would; at each beat
    # boundary log how much CPU this thread actually received (thread_time).
    wall_ms, cpu_ms = [], []
    spin = 0.0
    w_prev = time.perf_counter()
    c_prev = time.thread_time()
    w_next = w_prev + a.period
    while len(wall_ms) < a.beats:
        spin += 1.0
        if spin >= 1e6:
            spin = 0.0
        w = time.perf_counter()
        if w >= w_next:
            c = time.thread_time()
            wall_ms.append((w - w_prev) * 1000.0)
            cpu_ms.append((c - c_prev) * 1000.0)
            w_prev, c_prev = w, c
            w_next = w + a.period

    for p in procs:
        p.terminate()
    for p in procs:
        p.join(timeout=2)

    duty = [c / w for c, w in zip(cpu_ms, wall_ms)]
    assert all(0.0 < d <= 1.10 for d in duty), \
        f"duty out of sane range: min={min(duty):.4f} max={max(duty):.4f}"
    units = [70.0 * d for d in duty]

    with open(a.out, "w") as f:
        f.write(f"# recorded={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        f.write(f"# uname={' '.join(platform.uname())}\n")
        f.write(f"# python={platform.python_version()} cpu_count={os.cpu_count()}\n")
        f.write(f"# workers={a.workers} period_s={a.period} beats={a.beats}\n")
        f.write("beat,wall_ms,cpu_ms,duty,units\n")
        for k in range(a.beats):
            f.write(f"{k},{wall_ms[k]:.3f},{cpu_ms[k]:.3f},"
                    f"{duty[k]:.5f},{units[k]:.3f}\n")

    q = statistics.quantiles(duty, n=10)
    print(f"workers={a.workers} beats={a.beats} -> {a.out}")
    print(f"duty  mean={statistics.fmean(duty):.3f} "
          f"p10={q[0]:.3f} p50={q[4]:.3f} p90={q[8]:.3f}")
    print(f"units mean={statistics.fmean(units):.2f} "
          f"(70 = full availability = frozen base level)")
    print("replay maps units -> ms via units * KAPPA(6.052) * scale(cal/285)")


if __name__ == "__main__":
    main()
