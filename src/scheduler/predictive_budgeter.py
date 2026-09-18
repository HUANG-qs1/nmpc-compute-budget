"""PredictiveBudgeter v4: v3 online gates + Markov one-step risk prediction.
Asymmetric risk threshold (theta=0.10): pre-downgrade if P(next budget infeasible
for gear) > theta. Design basis: D17 analysis - timeout cost >> precision cost.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_budgeter import ComputeBudgeter

class PredictiveBudgeter(ComputeBudgeter):
    BUDGETS = (80.0, 40.0, 15.0)  # 充足/紧张/低谷
    P = ((0.90, 0.08, 0.02),
         (0.20, 0.70, 0.10),
         (0.15, 0.25, 0.60))

    def __init__(self, risk_theta=0.10, **kw):
        super().__init__(**kw)
        self.risk_theta = risk_theta

    def _state(self, budget_ms):
        return min(range(3), key=lambda i: abs(budget_ms - self.BUDGETS[i]))

    def _next_risk(self, np_, s):
        g = self._gate(np_)
        return sum(self.P[s][j] for j, bj in enumerate(self.BUDGETS) if bj < g)

    def decide(self, budget_ms):
        np_, gear = super().decide(budget_ms)
        s = self._state(budget_ms)
        gi = self.ORDER.index(gear)
        while gi > 0 and self._next_risk(self.GEARS[self.ORDER[gi]], s) > self.risk_theta:
            gi -= 1
        if gi != self.ORDER.index(gear):
            self.gear = self.ORDER[gi]
            self.last_np = self.GEARS[self.gear]
        return self.last_np, self.gear
