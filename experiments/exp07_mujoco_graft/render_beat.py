#!/usr/bin/env python3
"""i.8 render pipeline: beat-level doom-loop anatomy figure from an npz dump.
Usage: python3 render_beat.py DUMP.npz OUT.png
Panel order fixed: (a) solve time vs budget, (b) IPOPT iterations,
(c) position error, (d) horizon gear. Representative-run illustration;
quantitative claims always cite the full-batch CSV."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DT = 0.1
WARMUP_S = 1.0          # solver construction beats excluded from view
C_BUDGET = "#555555"    # gray
C_SOLVE  = "#0072B2"    # Okabe-Ito blue
C_TO     = "#D55E00"    # Okabe-Ito vermillion
C_ITER   = "#009E73"    # Okabe-Ito bluish green
C_ERR    = "#CC79A7"    # Okabe-Ito reddish purple
C_GEAR   = "#332288"    # indigo

plt.rcParams.update({
    "font.size": 10.5, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "grid.color": "#E3E3E3", "grid.linewidth": 0.6,
    "xtick.direction": "out", "ytick.direction": "out",
})

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python3 render_beat.py DUMP.npz OUT.png")
    path, out = sys.argv[1], sys.argv[2]
    d = np.load(path)
    skip = int(WARMUP_S / DT)
    n = len(d["errs"])
    t = np.arange(skip, n) * DT
    budget, ms = d["budgets"][skip:], d["tms"][skip:]
    to = d["timeouts"][skip:].astype(bool)
    its, errs, N = d["its"][skip:], d["errs"][skip:], d["N"][skip:]
    task, method, pattern = str(d["task"].item()), str(d["method"].item()), str(d["pattern"].item())
    seed, mm, scale = int(d["seed"]), float(d["mm"]), float(d["budget_scale"])
    to_all = int(d["timeouts"].sum()); emax = float(d["errs"].max())

    fig, ax = plt.subplots(4, 1, figsize=(9.5, 9.0), sharex=True)
    fig.suptitle("Beat-level anatomy: %s / %s / %s  (seed %d, mm=%.1f, budget scale %.2f)"
                 % (task, method, pattern, seed, mm, scale),
                 fontsize=12.5, fontweight="bold", y=0.985)
    fig.text(0.5, 0.955,
             "representative run | timeouts %d/%d | max error %.2f m | first %.1f s (solver warm-up) omitted"
             % (to_all, n, emax, WARMUP_S), ha="center", fontsize=9, color="#666666")

    # (a) solve time vs budget, log-y so doomed runs stay readable
    ax[0].step(t, budget, where="post", color=C_BUDGET, lw=1.2, label="compute budget")
    ax[0].plot(t, ms, color=C_SOLVE, lw=0.9, label="MPC solve time")
    ax[0].scatter(t[to], ms[to], s=16, facecolor=C_TO, edgecolor="white",
                  linewidth=0.4, zorder=5, label="timeout beat (hold last input)")
    ax[0].set_yscale("log")
    ax[0].set_ylim(max(5.0, ms[to == False].min() * 0.5 if (~to).any() else 5.0), None)
    ax[0].legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax[0].set_title("(a)", loc="left", fontweight="bold", fontsize=11)

    # (b) IPOPT iterations - doom-loop signature
    ax[1].plot(t, its, color=C_ITER, lw=0.9)
    ax[1].set_ylabel("IPOPT iterations")
    ax[1].set_ylim(0, max(12.0, float(its.max()) * 1.15))
    ax[1].set_title("(b)", loc="left", fontweight="bold", fontsize=11)

    # (c) position error, log-y
    ax[2].plot(t, errs, color=C_ERR, lw=0.9)
    ax[2].set_yscale("log")
    ax[2].set_ylabel("position error (m)")
    ax[2].set_title("(c)", loc="left", fontweight="bold", fontsize=11)

    # (d) horizon gear
    ax[3].step(t, N, where="post", color=C_GEAR, lw=1.1)
    ax[3].fill_between(t, 8, N, step="post", color=C_GEAR, alpha=0.15, lw=0)
    ax[3].set_ylabel("horizon N")
    ax[3].set_yticks([10, 15, 20])
    ax[3].set_ylim(8, 22)
    ax[3].set_xlabel("time (s)")
    ax[3].set_title("(d)", loc="left", fontweight="bold", fontsize=11)

    for a in ax:
        a.grid(axis="y")
    fig.tight_layout(rect=[0, 0, 1, 0.945])
    fig.savefig(out, dpi=200)
    print("saved ->", out)

if __name__ == "__main__":
    main()
