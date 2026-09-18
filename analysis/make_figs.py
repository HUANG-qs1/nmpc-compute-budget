#!/usr/bin/env python3
# make_figs.py - manuscript figures F2/F3/F6/F8/F1 (FIGSPEC.md D51 compliance; F2 seed 233->241 signed D56)
# panel letters bold 8pt top-left; labels 5-7pt at final size; Okabe-Ito fixed map
# vector SVG (font as path) + PNG 600dpi preview; numeric cross-checks asserted
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MM = 1 / 25.4
OI = {"v3": "#0072B2", "reactive": "#E69F00", "fixed20": "#D55E00", "fixed30": "#56B4E9"}
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D8 = ROOT + "/experiments/exp08_burst_scan"
D9 = ROOT + "/experiments/exp09_wmr_regress"
DATA = ROOT + "/experiments"
FIGS = ROOT + "/figs_out"
os.makedirs(FIGS, exist_ok=True)

plt.rcParams.update({
    "font.family": "Noto Sans", "font.size": 6.5,
    "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.labelsize": 7, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "legend.fontsize": 6, "lines.linewidth": 0.9, "lines.markersize": 3,
    "grid.linewidth": 0.4, "svg.fonttype": "path", "axes.unicode_minus": False,
})

from matplotlib.ticker import LogFormatter

class AsciiLogFormatter(LogFormatter):
    """Log tick labels with ASCII hyphen instead of U+2212 (Noto Sans lacks U+2212)."""
def __call__(self, x, pos=None):
        s = super().__call__(x, pos)
        return s.replace("\u2212", "-") if s else s

def ascii_log_ticks(ax, axis="y"):
    f = AsciiLogFormatter()
    if axis in ("y", "both"):
        ax.yaxis.set_major_formatter(f)
    if axis in ("x", "both"):
        ax.xaxis.set_major_formatter(f)

def panel_letter(ax, s, dx=-0.14):
    ax.text(dx, 1.03, s, transform=ax.transAxes, fontsize=8, fontweight="bold",
            va="top", ha="left")

def starvation_spans(budget, thresh=100.0):
    starv = budget < thresh
    edges = np.diff(starv.astype(int))
    starts = [0] if starv[0] else []
    starts += (np.where(edges == 1)[0] + 1).tolist()
    ends = (np.where(edges == -1)[0] + 1).tolist()
    if starv[-1]:
        ends.append(len(starv))
    return list(zip(starts, ends))

def shade_spans(ax, spans, t):
    for a, b in spans:
        ax.axvspan(t[a], t[min(b, len(t) - 1)], color="#D55E00", alpha=0.09, lw=0, zorder=0)

def load(name):
    z = np.load("%s/%s.npz" % (DATA, name), allow_pickle=True)
    return {k: (z[k].item() if z[k].shape == () else z[k]) for k in z.files}

# ============ F2: doom-loop vs v3 rescue anatomy, seed 241 (double column) ============
def build_f2():
    f20 = load("dump_f2_f20_241"); v3 = load("dump_f2_v3_241")
    assert f20["seed"] == v3["seed"] == 241 and f20["task"] == v3["task"] == "hover"
    assert f20["pattern"] == v3["pattern"] == "random"
    t = np.arange(1000) * 0.1
    spans = starvation_spans(v3["budgets"])
    death20 = int(np.argmax(f20["errs"] > 100)) + 1
    to_runs = np.diff(np.concatenate([[0], f20["timeouts"] > 0, [0]]).astype(int))
    perm_to = int(np.where(to_runs == 1)[0][-1])
    v3_to = int(v3["timeouts"].sum())
    assert death20 == 112 and perm_to == 58 and v3_to == 16
    assert f20["errs"].max() > 1e4 and v3["errs"].max() < 0.1
    print("F2 landmarks: f20 permTO@%d death@%d peakErr=%.0f | v3 TO=%d ticks maxErr=%.3f maxIts=%d"
          % (perm_to, death20, f20["errs"].max(), v3_to, v3["errs"].max(), v3["its"].max()))

    fig, (axa, axb, axc) = plt.subplots(3, 1, figsize=(174 * MM, 150 * MM), sharex=True,
                                        gridspec_kw={"height_ratios": [1.15, 0.85, 0.9],
                                                     "hspace": 0.16})
    for ax in (axa, axb, axc):
        shade_spans(ax, spans, t)
    axa.plot(t, f20["errs"], color=OI["fixed20"], lw=0.8, label="fixed20")
    axa.plot(t, v3["errs"], color=OI["v3"], lw=0.8, label="v3")
    axa.plot(t[death20 - 1], f20["errs"][death20 - 1], marker="x", color=OI["fixed20"],
             ms=5, mew=1.4, ls="none")
    axa.set_yscale("log"); axa.set_ylim(5e-3, 3e5)
    axa.axhline(100, color="#555", lw=0.6, ls=(0, (4, 2)))
    axa.text(99.3, 130, "divergence criterion 100 m", ha="right", va="bottom",
             fontsize=5.5, color="#555")
    axa.set_ylabel("tracking error (m)")
    axb.text(0.015, 0.94, "fixed20: permanent timeout begins (%.1f s)" % t[perm_to],
             transform=axb.transAxes, fontsize=5.5, color=OI["fixed20"], va="top", ha="left")
    axa.annotate("fixed20 diverges (%.1f s)" % t[death20], xy=(t[death20], 150),
                 xytext=(30, 1.8), fontsize=5.5, color=OI["fixed20"],
                 ha="left", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["fixed20"]))
    axa.annotate("v3 survives the full run\n(max_err = %.2f m)" % v3["errs"].max(),
                 xy=(60, v3["errs"][600]), xytext=(48, 0.012), fontsize=5.5, color=OI["v3"],
                 va="bottom", arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["v3"]))
    axa.legend(frameon=False, loc="upper left", handlelength=1.4, borderaxespad=0.3)
    panel_letter(axa, "a")

    axb.plot(t, f20["its"], color=OI["fixed20"], lw=0.7)
    axb.plot(t, v3["its"], color=OI["v3"], lw=0.7)
    to_ticks = np.where(f20["timeouts"] > 0)[0]
    axb.plot(t[to_ticks], np.full_like(to_ticks, 13.4, dtype=float), "v", color=OI["fixed20"],
             ms=1.4, mew=0.4)
    axb.set_ylabel("IPOPT iters"); axb.set_ylim(0, 16.5)
    axb.set_yticks([0, 4, 8, 12])
    axb.annotate("fixed20 times out every tick\n(iters pegged at cap)", xy=(t[300], 12.5),
                 xytext=(t[320], 7.6), fontsize=5.5, color=OI["fixed20"],
                 arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["fixed20"]))
    axb.annotate("v3: 4 iters, 16 isolated timeouts", xy=(t[500], 4), xytext=(t[520], 5.4),
                 fontsize=5.5, color=OI["v3"], va="bottom",
                 arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["v3"]))
    panel_letter(axb, "b")

    axc.plot(t, v3["budgets"], color="#333", lw=0.8, label="compute budget (same seed)")
    axc.plot(t, f20["tms"], color=OI["fixed20"], lw=0.6, alpha=0.85, label="solve time (fixed20)")
    axc.plot(t, v3["tms"], color=OI["v3"], lw=0.6, alpha=0.85, label="solve time (v3)")
    axc.set_yscale("log"); axc.set_ylabel("time (ms)"); axc.set_xlabel("time (s)")
    axc.legend(frameon=False, loc="upper right", ncol=3, handlelength=1.2, columnspacing=0.9)
    panel_letter(axc, "c")
    fig.align_ylabels()
    fix_log_axes(fig)
    for ext in ("svg", "png"):
        fig.savefig("%s/F2_anatomy_seed241.%s" % (FIGS, ext),
                    dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("F2 OK: %d starvation spans, %d starved ticks"
          % (len(spans), sum(b - a for a, b in spans)))


# apply ASCII log formatter to log axes (called after axes are set up)
def fix_log_axes(fig):
    for ax in fig.get_axes():
        if ax.get_yscale() == "log":
            ascii_log_ticks(ax, "y")
        if ax.get_xscale() == "log":
            ascii_log_ticks(ax, "x")

# ============ F3: gear timelines, v3@241 survives vs v3@233 diverges (single column) ============
def build_f3():
    sv = load("dump_f2_v3_241"); di = load("dump_div_v3")
    assert sv["method"] == di["method"] == "v3"
    t = np.arange(1000) * 0.1
    fig, axes = plt.subplots(2, 1, figsize=(84 * MM, 78 * MM), sharex=True,
                             gridspec_kw={"hspace": 0.30})
    for ax, d, tag, note in ((axes[0], sv, "a", "v3 @ seed 241 (hover/random): survives"),
                             (axes[1], di, "b", "v3 @ seed 233 (circle/burst): diverges")):
        spans = starvation_spans(d["budgets"])
        shade_spans(ax, spans, t)
        ax.plot(t, d["budgets"], color="#333", lw=0.7, label="budget")
        ax.set_yscale("log"); ax.set_ylim(20, 500)
        ax.set_yticks([50, 100, 200, 400]); ax.set_yticklabels(["50", "100", "200", "400"])
        ax.set_ylabel("budget (ms)")
        ax2 = ax.twinx()
        ax2.spines["right"].set_visible(True); ax2.spines["right"].set_linewidth(0.6)
        ax2.step(t, d["N"], where="post", color=OI["v3"], lw=1.0)
        ax2.set_ylim(8, 22); ax2.set_yticks([10, 15, 20])
        ax2.set_ylabel("gear $N_p$", color=OI["v3"])
        ax2.tick_params(axis="y", colors=OI["v3"], labelsize=6)
        to_ticks = np.where(d["timeouts"] > 0)[0]
        ax.plot(t[to_ticks], np.full_like(to_ticks, 24, dtype=float), "v", color=OI["fixed20"],
                ms=1.2, mew=0.35)
        n_to = len(to_ticks)
        gearL = float((d["N"] == 10).mean())
        print("F3 %s: TO=%d ticks, gearL=%.3f, gear changes=%d"
              % (tag, n_to, gearL, int((np.diff(d["N"]) != 0).sum())))
        ax.text(0.015, 0.93, note, transform=ax.transAxes, fontsize=5.5, color="#333",
                va="top", ha="left")
        ax.text(0.985, 0.93, "TO = %.1f%%   gearL = %.1f%%" % (n_to / 10, 100 * gearL),
                transform=ax.transAxes, fontsize=5, ha="right", va="top", color="#555")
        panel_letter(ax, tag, dx=-0.21)
    axes[1].set_xlabel("time (s)")
    fig.align_ylabels()
    fix_log_axes(fig)
    for ext in ("svg", "png"):
        fig.savefig("%s/F3_gear_timeline.%s" % (FIGS, ext),
                    dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("F3 OK")

# build_f2()  # npz dumps not in repo; F2/F3 frozen from v5
# build_f3()

# ============ F6: cross-platform cliff (quad exp08 vs WMR exp09), single column ============
import math, csv as _csv
import collections as _col

P_START = 0.0067
def duty_frac(blen):
    return P_START * blen / (1 + P_START * (blen - 1))

def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(_csv.DictReader(f))

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)

TASK_C = {"hover": "#333333", "step": "#009E73", "circle": "#0072B2", "fig8": "#D55E00"}

def build_f6():
    e8r = read_csv_rows("%s/20260911_exp08_scan_srv.csv" % D8)
    e9r_ = read_csv_rows("%s/20260912_exp09_regress_srv.csv" % D9)
    e9p = read_csv_rows("%s/20260912_exp09_probe_blen100_srv.csv" % D9)
    e9s = read_csv_rows("%s/20260913_exp09_scan_srv.csv" % D9)
    # quad exp08: v3 death>100 by (task, blen)
    d8c = _col.defaultdict(lambda: [0, 0])
    for r in e8r:
        if r["method"] != "v3": continue
        key = (r["task"], int(r["blen"]))
        d8c[key][1] += 1
        if float(r["max_err"]) > 100: d8c[key][0] += 1
    # WMR exp09: D49 merge, traj=fig8 pattern=burst, fixed20 death>5
    rows9 = []
    for r in e9r_:
        r = dict(r); r["blen"] = "30"; rows9.append(r)
    rows9 += [dict(r) for r in e9p] + [dict(r) for r in e9s]
    f8r = [r for r in rows9 if r["traj"] == "fig8" and r["pattern"] == "burst"]
    assert len(f8r) == 180
    d9c = _col.defaultdict(lambda: [0, 0])
    for r in f8r:
        key = (r["method"], int(r["blen"]))
        d9c[key][1] += 1
        if float(r["max_err"]) > 5.0: d9c[key][0] += 1
    # frozen cross-checks (D49/D55)
    assert d9c[("fixed20", 30)] == [0, 15] and d9c[("fixed20", 100)] == [6, 15]
    assert d9c[("fixed20", 110)] == [8, 15] and d9c[("v3", 100)] == [0, 15]
    assert d8c[("circle", 5)] == [6, 15] and d8c[("circle", 30)] == [11, 15]
    assert d8c[("hover", 30)] == [6, 15] and d8c[("fig8", 10)] == [4, 15]

    fig, (axa, axb) = plt.subplots(2, 1, figsize=(84 * MM, 100 * MM), sharex=True,
                                   gridspec_kw={"hspace": 0.32})
    blens8 = [5, 10, 15, 20, 30]
    for task in ["hover", "step", "circle", "fig8"]:
        xs = [100 * duty_frac(b) for b in blens8]
        ps, los, his = [], [], []
        for b in blens8:
            k, n = d8c[(task, b)]
            p, lo, hi = wilson(k, n)
            ps.append(100 * p); los.append(100 * (p - lo)); his.append(100 * (hi - p))
        kw = {}
        if task == "hover":  # identical counts to step; offset + dashed so both stay visible
            xs = [x - 0.3 for x in xs]
            kw["ls"] = (0, (4, 2))
        axa.errorbar(xs, ps, yerr=[los, his], color=TASK_C[task], lw=0.9, ms=2.6,
                     marker="o", capsize=1.2, capthick=0.5, elinewidth=0.5, label=task, **kw)
    axa.axhline(50, color="#999", lw=0.5, ls=(0, (3, 2)))
    axa.set_ylim(-4, 104); axa.set_ylabel("divergence rate (%)")
    axa.tick_params(axis="x", labelbottom=True)  # m8: panel (a) must show duty tick labels
    axa.legend(frameon=False, loc="upper left", fontsize=5.5, handlelength=1.2, borderaxespad=0.2)
    axa.text(0.97, 0.93, "quad (MuJoCo), v3", transform=axa.transAxes, ha="right",
             va="top", fontsize=6, color="#333")
    panel_letter(axa, "a")

    xs9 = [30, 40, 50, 60, 70, 80, 90, 100, 110, 130]
    xd = [100 * duty_frac(b) for b in xs9]
    ps, los, his = [], [], []
    for b in xs9:
        k, n = d9c[("fixed20", b)]
        p, lo, hi = wilson(k, n)
        ps.append(100 * p); los.append(100 * (p - lo)); his.append(100 * (hi - p))
    axb.errorbar(xd, ps, yerr=[los, his], color=OI["fixed20"], lw=0.9, ms=2.6, marker="o",
                 capsize=1.2, capthick=0.5, elinewidth=0.5, label="fixed20")
    for b in [30, 100]:
        k, n = d9c[("v3", b)]
        p, lo, hi = wilson(k, n)
        axb.errorbar([100 * duty_frac(b)], [100 * p], yerr=[[100 * (p - lo)], [100 * (hi - p)]],
                     color=OI["v3"], ms=2.6, marker="o", capsize=1.2, capthick=0.5,
                     elinewidth=0.5, label="v3" if b == 30 else None)
    axb.axhline(50, color="#999", lw=0.5, ls=(0, (3, 2)))
    axb.set_ylim(-4, 104); axb.set_ylabel("divergence rate (%)")
    axb.set_xlabel("burst duty cycle (%)")
    axb.legend(frameon=False, loc="upper left", fontsize=5.5, handlelength=1.2, borderaxespad=0.2)
    axb.text(0.97, 0.93, "WMR (CasADi), fig8/burst", transform=axb.transAxes, ha="right",
             va="top", fontsize=6, color="#333")
    panel_letter(axb, "b")
    # L50 annotations: quad v3 circle crosses 50% at ~6.9-8%; WMR fixed20 at ~42%
    axa.annotate("circle: L50 = 7.1% duty", xy=(100 * duty_frac(11.25), 50),
                 xytext=(30.5, 60), fontsize=5.5, color=TASK_C["circle"],
                 arrowprops=dict(arrowstyle="-", lw=0.5, color=TASK_C["circle"]))
    axb.annotate("fixed20: L50 = 42.0% duty", xy=(100 * duty_frac(107.5), 50),
                 xytext=(20, 72), fontsize=5.5, color=OI["fixed20"],
                 arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["fixed20"]))
    fig.align_ylabels()
    for ext in ("svg", "png"):
        fig.savefig("%s/F6_platform_cliff.%s" % (FIGS, ext),
                    dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("F6 OK: quad circle L50 duty=%.1f%%, WMR fixed20 L50 duty=%.1f%% (ratio %.1fx)"
          % (100 * duty_frac(11.25), 100 * duty_frac(107.5), duty_frac(107.5) / duty_frac(11.25)))

# ============ F8: exp08 dose-response landscape heatmaps, single column ============
def build_f8():
    e8r = read_csv_rows("%s/20260911_exp08_scan_srv.csv" % D8)
    blens = [5, 10, 15, 20, 30]; tasks = ["hover", "step", "circle", "fig8"]
    dd = _col.defaultdict(lambda: [0, 0])
    for r in e8r:
        key = (r["method"], r["task"], int(r["blen"]))
        dd[key][1] += 1
        if float(r["max_err"]) > 100: dd[key][0] += 1
    # frozen checks
    assert dd[("v3", "circle", 20)] == [11, 15] and dd[("fixed20", "fig8", 20)] == [13, 15]
    assert dd[("v3", "hover", 5)] == [0, 15] and dd[("fixed20", "circle", 5)] == [15, 15]
    fig, axes = plt.subplots(2, 1, figsize=(84 * MM, 96 * MM),
                             gridspec_kw={"hspace": 0.55})
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("div", ["#f7f7f7", "#F0C040", "#D55E00", "#7a2000"])
    for ax, meth, tag, title in ((axes[0], "v3", "a", "v3 (budget-aware)"),
                                 (axes[1], "fixed20", "b", "fixed20 (fixed horizon)")):
        M = np.zeros((4, 5))
        for i, task in enumerate(tasks):
            for j, b in enumerate(blens):
                k, n = dd[(meth, task, b)]
                M[i, j] = 100 * k / n
        im = ax.imshow(M, cmap=cmap, vmin=0, vmax=100, aspect="auto")
        for i in range(4):
            for j in range(5):
                k, n = dd[(meth, tasks[i], blens[j])]
                v = M[i, j]
                ax.text(j, i, "%d/15" % k, ha="center", va="center", fontsize=5,
                        color="white" if v > 55 else "#333")
        ax.set_xticks(range(5)); ax.set_xticklabels(["%d\n(%.0f%%)" % (b, 100 * duty_frac(b)) for b in blens], fontsize=5.5)
        ax.set_yticks(range(4)); ax.set_yticklabels(tasks, fontsize=6)
        ax.set_title(title, fontsize=6.5, loc="left", pad=2)
        ax.tick_params(length=0)
        for sp in ax.spines.values(): sp.set_visible(False)
        panel_letter(ax, tag, dx=-0.24)
    axes[1].set_xlabel("burst length (steps)  /  duty cycle (%)")
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("divergence rate (%)", fontsize=6); cb.ax.tick_params(labelsize=5.5)
    cb.outline.set_linewidth(0.5)
    for ext in ("svg", "png"):
        fig.savefig("%s/F8_dose_landscape.%s" % (FIGS, ext),
                    dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("F8 OK: v3 circle 40->73%%, fixed20 circle 100%% flat")

build_f6()
build_f8()


from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

def build_f1():
    fig, ax = plt.subplots(figsize=(174 * MM, 96 * MM))
    ax.set_xlim(0, 174); ax.set_ylim(0, 96); ax.axis("off")

    def box(x, y, w, h, lines, fc="#f5f5f5", ec="#333", fs=6.5, bold_first=True, lw=0.8):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6",
                                    fc=fc, ec=ec, lw=lw, mutation_scale=1))
        for i, ln in enumerate(lines):
            ax.text(x + w / 2, y + h - 3.6 - i * 3.7, ln, ha="center", va="center",
                    fontsize=fs, color="#333",
                    fontweight="bold" if (i == 0 and bold_first) else "normal")

    def arrow(x1, y1, x2, y2, label=None, lx=0, ly=2.0, color="#333", lw=0.9, fs=6, style="-|>"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                     mutation_scale=6, color=color, lw=lw, shrinkA=0, shrinkB=0))
        if label:
            ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha="center",
                    fontsize=fs, color=color)

    box(2, 66, 28, 24, ["compute budget", "nominal ~35-340 ms", "burst / periodic /", "random (seeded)"], fc="white")
    box(40, 66, 46, 24, ["ComputeBudgeter (v3)", "onboard calibration",
                         r"$b_{eff}=b \times calib / CALIB\_REF$", r"gate: $P^2$ q90 $< b_{eff}$"], fc="#e8f1f8")
    box(96, 66, 40, 24, ["NMPC solver", "CasADi + IPOPT", r"gear $N_p \in \{10,15,20\}$",
                         "hard deadline = budget"], fc="white")
    box(146, 66, 26, 24, ["plant", "quad (MuJoCo)", "or WMR"], fc="white")
    arrow(30, 78, 40, 78, "budget", ly=-3.4, fs=5.5)
    arrow(86, 78, 96, 78, "$N_p$,\niter cap", ly=-2.6, fs=5.5)
    arrow(136, 78, 146, 78, "u", ly=2.4)
    ax.plot([159, 159], [66, 56], color="#333", lw=0.8)
    ax.plot([116, 159], [56, 56], color="#333", lw=0.8)
    arrow(116, 56, 116, 66, lw=0.8)
    ax.text(137, 58.5, "state x", ha="center", fontsize=6, color="#333")
    ax.plot([106, 106], [66, 50], color="#333", lw=0.8)
    ax.plot([63, 106], [50, 50], color="#333", lw=0.8)
    arrow(63, 50, 63, 66, lw=0.8)
    ax.text(84, 52.5, r"solve time $t_k$", ha="center", fontsize=6, color="#333")
    box(40, 14, 66, 26, ["envelope calibration (Sec. 3.4)",
                         r"jitter $\epsilon=0.05$ | stratified $L \times \kappa$ | rolling",
                         "importance-weighted | ACI (200-tick window)",
                         "updates gate quantile online"], fc="#fdf3e7")
    arrow(55, 40, 52, 66, lw=0.8)
    ax.text(57.8, 52.5, "quantile bound", ha="center", va="center", fontsize=5.5, color="#333", rotation=-90)
    box(124, 14, 48, 26, ["outcome", "survive: error bounded", r"doom loop: timeout $\rightarrow$",
                          r"stale input $\rightarrow$ divergence"], fc="white")
    arrow(159, 56, 159, 40, lw=0.8)
    ax.plot([116, 116], [56, 27], color="#333", lw=0.8)
    ax.plot([116, 124], [27, 27], color="#333", lw=0.8)
    for ext in ("svg", "png"):
        fig.savefig("%s/F1_system.%s" % (FIGS, ext),
                    dpi=600 if ext == "png" else None, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("F1 OK")

# build_f1()  # schematic, unchanged
