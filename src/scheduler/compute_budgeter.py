"""ComputeBudgeter v1: L/M/H gear scheduling for compute-budget MPC.
Design locked in preregistration_v1.md (Day 10):
- gears: L=Np10, M=Np15, H=Np20 (Day 9 closed-loop evidence)
- EWMA filter + hysteresis + dwell time + timeout freeze
- feasibility precondition: gear allowed only if q90(gear) < budget
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "estimation"))
from p2_quantile import P2Quantile

HERE = os.path.dirname(os.path.abspath(__file__))

class ComputeBudgeter:
    # empirical q90 solve time per gear (ms), from Day 9 ext scan (circle+fig8, 10 seeds)
    Q90 = {10: 14.5, 15: 27.0, 20: 42.5}
    GEARS = {"L": 10, "M": 15, "H": 20}
    ORDER = ["L", "M", "H"]

    def __init__(self, alpha=0.3, hyst=0.15, dwell=5, budget_margin=1.0, use_freeze=True, online=False):
        self.alpha = alpha          # EWMA smoothing
        self.hyst = hyst            # hysteresis band (fraction of budget)
        self.dwell = dwell          # min steps between gear switches
        self.margin = budget_margin # feasibility slack: q90*margin < budget
        self.use_freeze = use_freeze
        self.online = online
        if online:  # per-gear P2 estimators, prior-seeded with static Q90
            self.est = {n: P2Quantile(0.9) for n in self.GEARS.values()}
            for n, e in self.est.items():
                for _ in range(5):
                    e.add(self.Q90[n])
        self.last_np = None
        self.gear = "M"             # start at middle gear
        self.ewma_ms = None         # EWMA of solve time
        self.since_switch = 999     # steps since last switch
        self.frozen = False         # timeout freeze flag
        self.log = []               # per-step decision log

    def _gate(self, np_):
        if self.online:
            est = self.est[np_].get()
            return est if est is not None else self.Q90[np_]
        return self.Q90[np_]

    def _feasible(self, gear, budget_ms):
        np_ = self.GEARS[gear]
        return self._gate(np_) * self.margin < budget_ms

    def _highest_feasible(self, budget_ms):
        for g in reversed(self.ORDER):
            if self._feasible(g, budget_ms):
                return g
        return "L"  # nothing feasible -> lowest gear (survival mode)

    def update_timing(self, solve_ms, timed_out):
        """Call after each solve with measured wall time."""
        if self.ewma_ms is None:
            self.ewma_ms = solve_ms
        else:
            self.ewma_ms = self.alpha * solve_ms + (1 - self.alpha) * self.ewma_ms
        self.frozen = timed_out if getattr(self, 'use_freeze', True) else False
        if getattr(self, 'online', False) and self.last_np is not None:
            self.est[self.last_np].add(solve_ms)

    def decide(self, budget_ms):
        """Return (Np, gear). Called once per control step BEFORE solve."""
        self.since_switch += 1
        target = self._highest_feasible(budget_ms)
        new_gear = self.gear
        ti = self.ORDER.index(target)
        ci = self.ORDER.index(self.gear)

        if ti < ci:
            # downgrade: always allowed immediately (safety first)
            new_gear = target
        elif ti > ci:
            # upgrade: needs dwell time + not frozen + hysteresis margin
            hyst_ok = self._gate(self.GEARS[target]) * (1 + self.hyst) * self.margin < budget_ms
            if self.since_switch >= self.dwell and not self.frozen and hyst_ok:
                new_gear = target

        if new_gear != self.gear:
            self.since_switch = 0
        self.gear = new_gear
        self.log.append({"budget": budget_ms, "gear": new_gear,
                         "ewma": self.ewma_ms, "frozen": self.frozen})
        self.last_np = self.GEARS[new_gear]
        return self.last_np, new_gear

    def save_log(self, path):
        with open(path, "w") as f:
            json.dump(self.log, f, indent=1)
