"""P² online quantile estimation (Jain & Chlamtac, 1985).
Tracks a target quantile in O(1) time/space per observation.
Used to learn per-gear q90 solve-time gates online (innovation 1).
"""

class P2Quantile:
    def __init__(self, p=0.9):
        self.p = p
        self.n = 0
        self.q = []      # 5 markers: min, p/2-ish, median-ish..., max
        self.pos = [1, 2, 3, 4, 5]
        self.desired = [1, 1 + 2*p, 1 + 4*p, 3 + 2*p, 5]
        self.incr = [0, p/2, p, (1+p)/2, 1]

    def add(self, x):
        self.n += 1
        if self.n <= 5:
            self.q.append(x)
            if self.n == 5:
                self.q.sort()
            return
        # find cell
        if x < self.q[0]:
            self.q[0] = x; k = 0
        elif x >= self.q[4]:
            self.q[4] = x; k = 3
        else:
            k = next(i for i in range(4) if self.q[i] <= x < self.q[i+1])
        for i in range(k+1, 5):
            self.pos[i] += 1
        for i in range(5):
            self.desired[i] += self.incr[i]
        # adjust markers 2-4
        for i in range(1, 4):
            d = self.desired[i] - self.pos[i]
            if (d >= 1 and self.pos[i+1] - self.pos[i] > 1) or \
               (d <= -1 and self.pos[i-1] - self.pos[i] < -1):
                ds = 1 if d >= 1 else -1
                qp = self._parabolic(i, ds)
                if self.q[i-1] < qp < self.q[i+1]:
                    self.q[i] = qp
                else:
                    self.q[i] = self._linear(i, ds)
                self.pos[i] += ds

    def _parabolic(self, i, d):
        m, mp, mm = self.pos[i], self.pos[i+1], self.pos[i-1]
        q, qp, qm = self.q[i], self.q[i+1], self.q[i-1]
        return q + d/(mp-mm) * ((m-mm+d)*(qp-q)/(mp-m) + (mp-m-d)*(q-qm)/(m-mm))

    def _linear(self, i, d):
        j = i + d
        return self.q[i] + d * (self.q[j]-self.q[i]) / (self.pos[j]-self.pos[i])

    def get(self):
        return self.q[2] if self.n >= 5 else None
