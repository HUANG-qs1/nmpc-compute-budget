#!/usr/bin/env python3
# make_figs_v5.py - v5 new figures: F11 five-arm divergence, F12 bsf sanity,
# F13 WMR v3 six-point (DR-6), F14 precision (DR-2). Okabe-Ito, English, 600dpi PNG+SVG.
# All numbers cross-checked against stats_memo_v5.md (assert).
import csv, math
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

MM = 1/25.4
OI = {"v3": "#0072B2", "reactive": "#E69F00", "fixed20": "#D55E00",
      "fixed10": "#56B4E9", "bsf": "#009E73"}
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = ROOT + "/experiments"
FIGS = ROOT + "/figs_out"
os.makedirs(FIGS, exist_ok=True)

class _AsciiMinus(mticker.LogFormatter):
    def __call__(self, x, pos=None):
        t = super().__call__(x, pos)
        return t.replace("\u2212", "-") if t else t

plt.rcParams.update({
    "font.family": "Noto Sans", "font.size": 6.5,
    "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.labelsize": 7, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "legend.fontsize": 6, "lines.linewidth": 0.9, "lines.markersize": 3,
    "grid.linewidth": 0.4, "svg.fonttype": "path", "axes.unicode_minus": False,
})

def load(p):
    with open(p) as f: return list(csv.DictReader(f))
def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k/n; den = 1+z*z/n
    c = (p+z*z/(2*n))/den; h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (max(0.0, c-h), min(1.0, c+h))
def duty(blen, P=0.0067): return 100.0*P*blen/(1+P*(blen-1))
def panel_letter(ax, s, dx=-0.14):
    ax.text(dx, 1.03, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="top", ha="left")

G2 = load(f"{DATA}/exp07_mujoco_graft/20260909_exp07_graft_srv2.csv")
QR = load(f"{DATA}/exp07_mujoco_graft/exp10_quad.csv")
QALL = G2 + QR
for r in QALL: r["div"] = float(r["max_err"]) > 100.0
M5 = ["fixed20", "reactive", "fixed10", "v3", "bsf"]
TASKS = ["hover", "step", "circle", "fig8"]

# sanity assert vs memo
assert sum(r["div"] for r in QALL if r["method"]=="bsf") == 0
assert sum(r["div"] for r in QALL if r["method"]=="fixed10") == 87
assert sum(r["div"] for r in QALL if r["method"]=="v3") == 149

# ---------------- F11: five-arm divergence by task + overall ----------------
def build_f11():
    fig, ax = plt.subplots(figsize=(174*MM, 62*MM))
    groups = TASKS + ["overall"]
    nb, w = len(M5), 0.16
    x = np.arange(len(groups))
    for i, m in enumerate(M5):
        ys, lo, hi, ns = [], [], [], []
        for g in groups:
            rows = [r for r in QALL if r["method"]==m and (g=="overall" or r["task"]==g)]
            k, n = sum(r["div"] for r in rows), len(rows)
            ci = wilson(k, n)
            ys.append(100*k/n); lo.append(max(0.0,100*(k/n-ci[0]))); hi.append(max(0.0,100*(ci[1]-k/n))); ns.append(n)
        pos = x + (i-(nb-1)/2)*w
        ax.bar(pos, ys, w*0.92, color=OI[m], label=m, zorder=3,
               yerr=[lo, hi], error_kw=dict(lw=0.6, capsize=1.2, capthick=0.6, ecolor="#444"))
        for px, y, k_, h_ in zip(pos, ys, [sum(r["div"] for r in QALL if r["method"]==m and (g=="overall" or r["task"]==g)) for g in groups], hi):
            if k_ == 0:
                ax.text(px, y + h_ + 1.2, "0/" + ("360" if px > 3.5 else "90"), ha="center", va="bottom",
                        fontsize=5.2, color=OI[m], fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylabel("divergence rate (%)"); ax.set_ylim(0, 108)
    ax.axvline(3.5, color="#999", lw=0.5, ls=":")
    ax.legend(ncol=5, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.04), columnspacing=1.0, handlelength=1.2)
    ax.text(3.52, 104, "n=90 per task cell; n=360 overall; Wilson 95% CI", fontsize=5.5, color="#555", va="top")
    fig.tight_layout()
    fig.savefig(f"{FIGS}/F11_five_arm.png", dpi=600); fig.savefig(f"{FIGS}/F11_five_arm.svg")
    plt.close(fig)

# ---------------- F12: bsf sanity (timeout / iter / time distributions) ----------------
def build_f12():
    import statistics as st
    fig, axes = plt.subplots(1, 4, figsize=(174*MM, 52*MM))
    cols = [("timeout_rate", "timeout rate (run mean)", (0, 1.12)),
            ("iter_mean", "IPOPT iterations (run mean)", (0, 34)),
            ("time_q50", "median solve time per step (ms)", (0, 322))]
    M4 = ["fixed20", "fixed10", "v3", "bsf"]
    for ax, (c, lab, ylim) in zip(axes, cols):
        data = [[float(r[c]) for r in QALL if r["method"]==m] for m in M4]
        bp = ax.boxplot(data, vert=True, widths=0.55, patch_artist=True, showfliers=False,
                        medianprops=dict(color="black", lw=0.8), whiskerprops=dict(lw=0.6),
                        capprops=dict(lw=0.6), boxprops=dict(lw=0.6))
        for patch, m in zip(bp["boxes"], M4): patch.set_facecolor(OI[m]); patch.set_alpha(0.75)
        ax.set_xticks(range(1, len(M4)+1)); ax.set_xticklabels(M4, rotation=18, ha="right")
        ax.set_ylabel(lab); ax.set_ylim(*ylim)
        span = ylim[1] - ylim[0]
        for i, d in enumerate(data):
            d = np.asarray(d)
            m_ = np.mean(d)
            ax.scatter([i+1], [m_], marker="D", s=8, color="black", zorder=5)
            lab = f"{m_:.2f}" if c != "time_q50" else f"{m_:.0f}"
            q1, q3 = np.percentile(d, [25, 75]); fence = q3 + 1.5*(q3-q1)
            wh = max(v for v in d if v <= fence + 1e-9)  # drawn whisker top (mpl default)
            bb = dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.4)
            if wh + 0.03*span <= ylim[1] - 0.03*span:
                ax.text(i+1, wh + 0.03*span, lab, ha="center", va="bottom", fontsize=5.5, color="#333", bbox=bb)
            else:
                ax.text(i+1, ylim[1] - 0.015*span, lab, ha="center", va="top", fontsize=5.5, color="#333", bbox=bb)

    # panel (d): survivor max_err median per arm (M3 review fix; frozen values asserted)
    axd = axes[3]
    meds, ns = [], []
    for m in M4:
        surv = [float(r["max_err"]) for r in QALL if r["method"] == m and not r["div"]]
        meds.append(st.median(surv)); ns.append(len(surv))
    exp_med = {"bsf": 0.40, "fixed20": 0.28, "fixed10": 0.51, "v3": 0.37}
    for m, md in zip(M4, meds):
        assert abs(md - exp_med[m]) < 0.005, (m, md)
    bars = axd.bar(range(4), meds, width=0.6, color=[OI[m] for m in M4], alpha=0.85, lw=0)
    axd.set_xticks(range(4))
    axd.set_xticklabels([f"{m}\n(n={n})" for m, n in zip(M4, ns)], rotation=18, ha="right", fontsize=5.2)
    for i, md in enumerate(meds):
        axd.text(i, md + 0.012, f"{md:.2f}", ha="center", va="bottom", fontsize=5.5, color="#333")
    axd.set_ylabel("survivor max err (m)"); axd.set_ylim(0, 0.68)

    panel_letter(axes[0], "a"); panel_letter(axes[1], "b"); panel_letter(axes[2], "c"); panel_letter(axes[3], "d")
    axes[0].set_title("bsf still times out (mean 25.6% of steps)", fontsize=6, color="#333", pad=9, loc="left")
    fig.text(0.005, 0.012, "boxes: median/IQR with whiskers; black diamond and number: run-mean",
             fontsize=5.2, color="#555")
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(f"{FIGS}/F12_bsf_sanity.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{FIGS}/F12_bsf_sanity.svg", bbox_inches="tight")
    plt.close(fig)

# ---------------- F13: WMR v3 six-point zero divergence (DR-6) ----------------
def build_f13():
    g9 = load(f"{DATA}/exp09_wmr_regress/20260912_exp09_regress_srv.csv")
    p9 = load(f"{DATA}/exp09_wmr_regress/20260912_exp09_probe_blen100_srv.csv")
    s9 = load(f"{DATA}/exp09_wmr_regress/20260913_exp09_scan_srv.csv")
    WR = load(f"{DATA}/exp09_wmr_regress/exp10_wmr.csv")
    wdiv = lambda r: float(r["max_err"]) > 5.0
    blens9 = [40,50,60,70,80,90,100,110,130]
    fx, fx_n = [], []
    for b in blens9:
        if b == 100: rows = [r for r in p9 if r["method"]=="fixed20" and r.get("traj","fig8")=="fig8"]
        else: rows = [r for r in s9 if r["method"]=="fixed20" and r["traj"]=="fig8" and int(float(r["blen"]))==b]
        fx.append(sum(wdiv(r) for r in rows)); fx_n.append(len(rows))
    assert fx == [0,0,2,1,1,4,6,8,7], fx
    v3pt = {}
    for r in g9:
        if r["method"]=="v3": v3pt.setdefault(30, [0,0]); v3pt[30][1]+=1; v3pt[30][0]+=wdiv(r)
    for src, bb in ((p9, 100),):
        for r in src:
            if r["method"]=="v3": v3pt.setdefault(bb, [0,0]); v3pt[bb][1]+=1; v3pt[bb][0]+=wdiv(r)
    for r in WR:
        b = int(float(r["blen"]))
        v3pt.setdefault(b, [0,0]); v3pt[b][1]+=1; v3pt[b][0]+=wdiv(r)
    assert all(v[0]==0 for v in v3pt.values())

    fig, ax = plt.subplots(figsize=(120*MM, 58*MM))
    D = [duty(b) for b in blens9]
    rate = [100*k/n for k, n in zip(fx, fx_n)]
    lo = [100*(k/n-wilson(k,n)[0]) for k, n in zip(fx, fx_n)]
    hi = [100*(wilson(k,n)[1]-k/n) for k, n in zip(fx, fx_n)]
    ax.errorbar(D, rate, yerr=[lo, hi], color=OI["fixed20"], marker="o", ms=3, lw=1.0,
                capsize=1.2, capthick=0.6, elinewidth=0.6, label="fixed20 (fig8/burst)")
    vb = sorted(v3pt); vD = [duty(b) for b in vb]
    vrate = [100*v3pt[b][0]/v3pt[b][1] for b in vb]
    vhi = [100*(wilson(v3pt[b][0],v3pt[b][1])[1]-v3pt[b][0]/v3pt[b][1]) for b in vb]
    ax.errorbar(vD, vrate, yerr=[[0]*len(vb), vhi], color=OI["v3"], marker="s", ms=3, lw=1.0,
                capsize=1.2, capthick=0.6, elinewidth=0.6, label="v3 (fig8; 16.8% point pools 4 patterns, n=60)")
    for b, d in zip(vb, vD):
        ax.annotate(f"0/{v3pt[b][1]}", (d, 0), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=5.2, color=OI["v3"])
    ax.axhline(50, color="#888", lw=0.6, ls="--")
    ax.annotate("fixed20: L50 = 42.0% duty [37.6, 45.7]", xy=(42.0, 50), xytext=(24, 66),
                fontsize=6, color=OI["fixed20"], arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["fixed20"]))
    ax.annotate("v3: L50 > 51.9% duty (not observed)", xy=(50.5, 1.0), xytext=(27.5, 13),
                fontsize=6, color=OI["v3"], arrowprops=dict(arrowstyle="-", lw=0.5, color=OI["v3"]))
    ax.set_xlabel("burst duty cycle (%)"); ax.set_ylabel("divergence rate (%)")
    ax.set_ylim(-4, 108); ax.set_xlim(12, 58)
    ax.legend(frameon=False, loc="upper left", fontsize=5.8)
    ax.text(0.98, 0.97, "WMR, divergence criterion max err > 5 m; Wilson 95% CI", transform=ax.transAxes,
            ha="right", va="top", fontsize=5.2, color="#555")
    fig.tight_layout()
    fig.savefig(f"{FIGS}/F13_wmr_v3_sixpoint.png", dpi=600); fig.savefig(f"{FIGS}/F13_wmr_v3_sixpoint.svg")
    plt.close(fig)

# ---------------- F14: precision mixed evidence (DR-2) ----------------
def build_f14():
    import statistics as st
    def boot_med(x, B=2000, seed=0):
        rng = np.random.default_rng(seed); x = np.asarray(x)
        return np.percentile(np.median(x[rng.integers(0, len(x), size=(B, len(x)))], axis=1), [2.5, 97.5])
    M3 = ["v3", "fixed10", "bsf"]
    fig, axes = plt.subplots(1, 2, figsize=(174*MM, 56*MM))
    nb, w = len(M3), 0.24
    x = np.arange(len(TASKS))
    for ax, mode in zip(axes, ["survivor", "itt"]):
        for i, m in enumerate(M3):
            ys, lo, hi, ns = [], [], [], []
            for t in TASKS:
                rows = [r for r in QALL if r["method"]==m and r["task"]==t]
                if mode == "survivor":
                    vals = [float(r["rmse"]) for r in rows if not r["div"]]
                else:
                    vals = [100.0 if r["div"] else float(r["rmse"]) for r in rows]
                med = st.median(vals); ci = boot_med(vals)
                ys.append(med); lo.append(max(med-ci[0], med*0.05+1e-4)); hi.append(ci[1]-med); ns.append(len(vals))
            pos = x + (i-(nb-1)/2)*w
            ax.errorbar(pos, ys, yerr=[lo, hi], color=OI[m], marker="o", ms=3, lw=0.9,
                        capsize=1.2, capthick=0.6, elinewidth=0.6, label=m)
            for px, y, n_ in zip(pos, ys, ns):
                if mode == "survivor" and m != "bsf":
                    off = (0, 7) if m == "v3" else (0, -11)
                    ax.annotate(f"{n_}", (px, y), textcoords="offset points", xytext=off,
                                ha="center", fontsize=5.0, color=OI[m],
                                bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.4))
        ax.set_yscale("log"); ax.set_xticks(x); ax.set_xticklabels(TASKS)
        ax.yaxis.set_major_formatter(_AsciiMinus()); ax.yaxis.set_minor_formatter(mticker.NullFormatter())
        ax.set_ylim(8e-3 if mode=="survivor" else 5e-2, 300)
        if mode == "itt":
            ax.axhline(100, color="#888", lw=0.6, ls="--")
            ax.text(3.45, 115, "penalty 100 m", fontsize=5.2, color="#666", ha="right")
    axes[0].set_ylabel("survivor RMSE median (m, log)")
    axes[1].set_ylabel("ITT RMSE median (m, log)")
    axes[0].set_title("survivors only (n annotated; selection effect)", fontsize=6, color="#333", pad=2)
    axes[1].set_title("intention-to-treat (diverged run = 100 m)", fontsize=6, color="#333", pad=2)
    axes[0].legend(frameon=False, loc="upper left", fontsize=5.8)
    axes[0].text(0.02, -0.17, "survivor n annotated (v3 above, fixed10 below; bsf always 90/90)",
                 transform=axes[0].transAxes, fontsize=5.0, color="#666")
    panel_letter(axes[0], "a"); panel_letter(axes[1], "b")
    fig.tight_layout()
    fig.savefig(f"{FIGS}/F14_precision_mixed.png", dpi=600); fig.savefig(f"{FIGS}/F14_precision_mixed.svg")
    plt.close(fig)

# ---------------- F4: quad dose-response, circle task (paper Fig. 5) ----------------
E8CSV = ROOT + "/experiments/exp08_burst_scan/20260911_exp08_scan_srv.csv"
G9 = f"{DATA}/exp09_wmr_regress/20260912_exp09_regress_srv.csv"
P9 = f"{DATA}/exp09_wmr_regress/20260912_exp09_probe_blen100_srv.csv"
S9 = f"{DATA}/exp09_wmr_regress/20260913_exp09_scan_srv.csv"

def boot_med(x, B=2000, seed=0):
    rng = np.random.default_rng(seed); x = np.asarray(x)
    return np.percentile(np.median(x[rng.integers(0, len(x), size=(B, len(x)))], axis=1), [2.5, 97.5])

def build_f4():
    import statistics as st
    e8 = load(E8CSV)
    BL = [5, 10, 15, 20, 30]
    fig, (axa, axb) = plt.subplots(2, 1, figsize=(88*MM, 112*MM),
                                   gridspec_kw={"hspace": 0.42, "height_ratios": [1, 1]})
    # frozen cross-checks
    cnt = {}
    for m in ("v3", "fixed20"):
        for b in BL:
            rows = [r for r in e8 if r["method"] == m and r["task"] == "circle" and int(r["blen"]) == b]
            cnt[(m, b)] = (sum(float(r["max_err"]) > 100 for r in rows), len(rows))
    assert cnt[("v3", 5)] == (6, 15) and cnt[("v3", 30)] == (11, 15), cnt
    assert all(cnt[("fixed20", b)] == (15, 15) for b in BL), cnt
    D = [duty(b) for b in BL]
    for m, mk, lab in (("v3", "o", "v3 (ours)"), ("fixed20", "s", "fixed20")):
        ps = [100*cnt[(m, b)][0]/cnt[(m, b)][1] for b in BL]
        lo = [100*(cnt[(m, b)][0]/cnt[(m, b)][1] - wilson(*cnt[(m, b)])[0]) for b in BL]
        hi = [100*(wilson(*cnt[(m, b)])[1] - cnt[(m, b)][0]/cnt[(m, b)][1]) for b in BL]
        axa.errorbar(D, ps, yerr=[lo, hi], color=OI[m], marker=mk, ms=3.4, lw=1.1,
                     capsize=1.4, capthick=0.6, elinewidth=0.6, label=lab)
    axa.set_ylim(-4, 112); axa.set_ylabel("divergence rate (%)")
    axa.set_xlim(1.5, 18.5)
    axa.tick_params(axis="x", labelbottom=False)
    axa.yaxis.set_ticks([0, 20, 40, 60, 80, 100])
    axa.grid(axis="y", color="#e5e5e5", lw=0.4, zorder=0)
    axt = axa.twiny()
    axt.set_xlim(axa.get_xlim()); axt.spines.top.set_visible(True)
    axt.set_xticks(D); axt.set_xticklabels([str(b) for b in BL])
    axt.set_xlabel("burst length (steps)", fontsize=6.5, labelpad=3)
    axt.tick_params(length=2)
    panel_letter(axa, "a")
    # panel (b): survivor rmse medians + bootstrap band
    meds, lob, hib = [], [], []
    for b in BL:
        vals = [float(r["rmse"]) for r in e8 if r["method"] == "v3" and r["task"] == "circle"
                and int(r["blen"]) == b and float(r["max_err"]) <= 100]
        meds.append(st.median(vals)); ci = boot_med(vals); lob.append(ci[0]); hib.append(ci[1])
    assert abs(meds[0]-0.1401) < 5e-4 and abs(meds[-1]-0.2061) < 5e-4, meds
    axb.fill_between(D, lob, hib, color=OI["v3"], alpha=0.16, lw=0)
    axb.plot(D, meds, color=OI["v3"], marker="o", ms=3.4, lw=1.1)
    axb.set_yscale("log")
    axb.set_ylim(0.1, 2.0)
    axb.yaxis.set_ticks([0.1, 0.2, 0.5, 1.0, 2.0])
    axb.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:g}"))
    axb.yaxis.set_minor_formatter(mticker.NullFormatter())
    axb.set_ylabel("median rmse (survivors)")
    axb.set_xlabel("burst duty cycle (%)")
    axb.set_xlim(1.5, 18.5)
    axb.grid(axis="y", color="#e5e5e5", lw=0.4, zorder=0)
    axb.annotate("fixed20: 0 survivors at all blen", xy=(0.04, 0.93), xycoords="axes fraction",
                 fontsize=6, color=OI["fixed20"], va="top")
    panel_letter(axb, "b")
    fig.legend(*axa.get_legend_handles_labels(), loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.4, columnspacing=1.2)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(f"{FIGS}/F4_quad_dose_response.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{FIGS}/F4_quad_dose_response.svg", bbox_inches="tight")
    plt.close(fig)
    print("F4 OK:", {k: v for k, v in cnt.items() if k[0] == "v3"})

# ---------------- F5: WMR dose-response (paper Fig. 7) ----------------
def build_f5():
    g9, p9, s9 = load(G9), load(P9), load(S9)
    wdiv = lambda r: float(r["max_err"]) > 5.0
    BL = [30, 40, 50, 60, 70, 80, 90, 100, 110, 130]
    fx, v3z = {}, {}
    for b in BL:
        if b == 30:
            frows = [r for r in g9 if r["method"] == "fixed20" and r["traj"] == "fig8" and r["pattern"] == "burst"]
            vrows = [r for r in g9 if r["method"] == "v3" and r["traj"] == "fig8" and r["pattern"] == "burst"]
        elif b == 100:
            frows = [r for r in p9 if r["method"] == "fixed20"]
            vrows = [r for r in p9 if r["method"] == "v3"]
        else:
            frows = [r for r in s9 if r["method"] == "fixed20" and r["traj"] == "fig8" and int(float(r["blen"])) == b]
            vrows = []
        fx[b] = (sum(wdiv(r) for r in frows), len(frows))
        if vrows: v3z[b] = (sum(wdiv(r) for r in vrows), len(vrows))
    assert [fx[b] for b in BL] == [(0,15),(0,15),(0,15),(2,15),(1,15),(1,15),(4,15),(6,15),(8,15),(7,15)], fx
    assert v3z == {30: (0, 15), 100: (0, 15)}, v3z
    D = [duty(b) for b in BL]
    rate = [100*fx[b][0]/fx[b][1] for b in BL]
    lo = [100*(fx[b][0]/fx[b][1]-wilson(*fx[b])[0]) for b in BL]
    hi = [100*(wilson(*fx[b])[1]-fx[b][0]) for b in BL]
