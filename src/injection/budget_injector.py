# -*- coding: utf-8 -*-
"""budget_injector.py - 预算注入器 v1
真实负载挤占: 独立 CPU 压测进程(忙循环)按预算档位启停
预算语义: B_k = 本拍允许求解器使用的最大 wall-clock(ms)
"""
import multiprocessing as mp
import time
import numpy as np

def _busy_loop(stop_flag):
    """压测进程: 纯 CPU 忙循环"""
    x = 0.0
    while not stop_flag.is_set():
        x += 1.0
        x = x % 1e6

class BudgetInjector:
    """按预算档位启停 CPU 压测进程, 实现真实资源挤占"""
    def __init__(self, n_workers=None, low_budget_ms=20.0):
        self.n_workers = n_workers or max(1, mp.cpu_count() - 1)
        self.low_budget_ms = low_budget_ms
        self._stop = mp.Event()
        self._procs = []

    def start_stress(self):
        if self._procs: return
        self._stop.clear()
        self._procs = [mp.Process(target=_busy_loop, args=(self._stop,), daemon=True)
                       for _ in range(self.n_workers)]
        for p in self._procs: p.start()

    def stop_stress(self):
        self._stop.set()
        for p in self._procs: p.join(timeout=2)
        self._procs = []

    def apply(self, budget_ms):
        """按当前预算决定压测启停: 低于低档阈值则挤占"""
        if budget_ms <= self.low_budget_ms:
            self.start_stress()
        else:
            self.stop_stress()
