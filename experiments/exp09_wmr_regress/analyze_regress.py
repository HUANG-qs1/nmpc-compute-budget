# -*- coding: utf-8 -*-
"""analyze_regress.py - exp09 WMR 回归复测判决器 (D48, v2 表头列名索引)
判决定位: 复现性核对, 不设 PASS/FAIL 门 (用户签字, 不触发 D48 压测门)
发散定义: max_err > 5.0 (D48 冻结, 先于 exp09 数据; 依据: exp06 健康峰值 1.02m,
          路径尺度 circle r=2.0 / fig8 a=3.0, 阈值=路径尺度 1.7-2.5 倍)
预登记期望(先于数据):
  blen=30 主批: fig8/burst 格 fixed20 发散率明显高于 v3; periodic 格均不发散
  blen=100 探针: 全分支覆盖 (见 run_regress.py 文档行), 描述性核对
v2: 按表头列名索引, 兼容 17 列(无 blen, 视为 30)与 18 列两种 CSV
用法: python3 analyze_regress.py CSV
stdlib 纯血 (cbmpc 无 pandas)
"""
import sys, statistics

DIV_MAX_ERR = 5.0  # D48 冻结, 先于数据
SEEDS = set(range(430, 445))
REQUIRED = ("traj", "method", "pattern", "seed", "max_err",
            "timeout_rate", "iter_mean", "time_drift")
TRAJS, PATTERNS, METHODS = ("circle", "fig8"), ("periodic", "burst"), ("v3", "fixed20")

def load(path):
    with open(path) as f:
        hdr = f.readline().strip().split(",")
        idx = {name: i for i, name in enumerate(hdr)}
        for name in REQUIRED:
            assert name in idx, "missing column " + name
        rows = []
        for ln, line in enumerate(f, 2):
            p = line.strip().split(",")
            assert len(p) == len(hdr), "line %d: %d fields != %d" % (ln, len(p), len(hdr))
            rows.append(p)
    return idx, rows

def fnum(x, name, ln):
    try:
        return float(x)
    except ValueError:
        raise AssertionError("line %d: bad numeric %s=%r" % (ln, name, x))

def blen_of(p, idx):
    return int(p[idx["blen"]]) if "blen" in idx else 30

def audit(idx, rows):
    print("=== AUDIT ===")
    print("rows: %d" % len(rows))
    seen = {}
    for p in rows:
        assert p[idx["traj"]] in TRAJS and p[idx["pattern"]] in PATTERNS \
            and p[idx["method"]] in METHODS, "bad vocab: %s" % str(p[:3])
        s = int(p[idx["seed"]])
        assert s in SEEDS, "seed %d outside 430-444 (smoke 95 must not appear)" % s
        key = (p[idx["traj"]], p[idx["method"]], p[idx["pattern"]], blen_of(p, idx), s)
        assert key not in seen, "duplicate cell %s" % (key,)
        seen[key] = True
    cells = {}
    for (t, m, pa, bl, s) in seen:
        cells.setdefault((t, m, pa, bl), []).append(s)
    partial = False
    for k in sorted(cells):
        ss = sorted(cells[k])
        miss = sorted(SEEDS - set(ss))
        print("cell %s: n=%d%s" % (k, len(ss), (" missing seeds %s" % miss) if miss else ""))
        if len(ss) != 15 or miss:
            partial = True
    if partial:
        print("!! PARTIAL CSV -- checks below are plumbing checks, NOT results !!")
    print("audit done")
    return not partial

def main(path):
    idx, rows = load(path)
    full = audit(idx, rows)
    num = {}
    for p in rows:
        num.setdefault((p[idx["traj"]], p[idx["pattern"]], blen_of(p, idx), p[idx["method"]]), []).append(p)
    print()
    print("=== per-cell summary (div = max_err > %.1f, frozen pre-data) ===" % DIV_MAX_ERR)
    print("%-7s %-8s %-5s %-8s %4s %6s | %8s %8s | %7s %7s | %7s" % (
        "traj", "pattern", "blen", "method", "n", "div", "TO_med", "TO_max",
        "it_div", "it_surv", "drift_q95"))
    gaps = {}
    for t in TRAJS:
        for pa in PATTERNS:
            blens = sorted({k[2] for k in num if k[0] == t and k[1] == pa})
            for bl in blens:
                for m in METHODS:
                    cell = num.get((t, pa, bl, m), [])
                    divs, tos, it_d, it_s, drifts = 0, [], [], [], []
                    for p in cell:
                        me = fnum(p[idx["max_err"]], "max_err", 0)
                        to = fnum(p[idx["timeout_rate"]], "timeout_rate", 0)
                        it = fnum(p[idx["iter_mean"]], "iter_mean", 0)
                        dr = fnum(p[idx["time_drift"]], "time_drift", 0)
                        tos.append(to); drifts.append(dr)
                        if me > DIV_MAX_ERR:
                            divs += 1; it_d.append(it)
                        else:
                            it_s.append(it)
                    rate = divs / max(len(cell), 1)
                    gaps[(t, pa, bl, m)] = rate
                    print("%-7s %-8s %-5d %-8s %4d %2d/%-2d %5.1f%% | %8.4f %8.4f | %7s %7s | %7.4f" % (
                        t, pa, bl, m, len(cell), divs, len(cell), 100 * rate,
                        statistics.median(tos) if tos else float("nan"),
                        max(tos) if tos else float("nan"),
                        ("%.1f" % statistics.median(it_d)) if it_d else "-",
                        ("%.1f" % statistics.median(it_s)) if it_s else "-",
                        sorted(drifts)[int(0.95 * (len(drifts) - 1))] if drifts else float("nan")))
                g = gaps.get((t, pa, bl, "fixed20"), 0.0) - gaps.get((t, pa, bl, "v3"), 0.0)
                print("    -> %s/%s blen=%d div gap (fixed20 - v3) = %+.1fpp" % (t, pa, bl, 100 * g))
    print()
    print("=== direction check (DESCRIPTIVE, reads back the pre-registered expectation) ===")
    if ("fig8", "burst", 30, "fixed20") in gaps:
        g30 = gaps[("fig8", "burst", 30, "fixed20")] - gaps[("fig8", "burst", 30, "v3")]
        print("fig8/burst blen=30 gap = %+.1fpp; expectation: fixed20 >> v3 -> direction %s" % (
            100 * g30, "REPLICATED" if g30 > 0 else "NOT REPLICATED"))
    if ("fig8", "burst", 100, "fixed20") in gaps:
        d_f, d_v = gaps[("fig8", "burst", 100, "fixed20")], gaps[("fig8", "burst", 100, "v3")]
        branch = "(a) cliff in (30,100], v3 rescues" if (d_f > 0 and d_v == 0) else \
                 ("(b) no finite cliff at this scale" if (d_f == 0 and d_v == 0) else \
                  "(c) cliff exists, v3 cannot rescue" if (d_f > 0 and d_v > 0) else \
                  "(unexpected) v3 div > fixed20 div -- inspect data")
        print("fig8/burst blen=100: fixed20 %.1f%% v3 %.1f%% -> probe branch %s" % (
            100 * d_f, 100 * d_v, branch))
    if not full:
        print("!! partial CSV: all numbers above are plumbing checks only !!")

if __name__ == "__main__":
    main(sys.argv[1])
