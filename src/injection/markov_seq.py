# -*- coding: utf-8 -*-
"""markov_seq.py - 预算时间戳序列生成
三状态马尔可夫链(充足/紧张/低谷) + 四类预算模式
所有序列种子可控、可复现
"""
import numpy as np

def gen_markov_seq(n, seed, budgets=(80.0, 40.0, 15.0),
                   P=((0.90, 0.08, 0.02), (0.20, 0.70, 0.10), (0.15, 0.25, 0.60))):
    """三状态马尔可夫链, 返回逐拍预算(ms)序列"""
    rng = np.random.default_rng(seed)
    s, out = 0, []
    for _ in range(n):
        out.append(budgets[s])
        s = rng.choice(3, p=P[s])
    return np.array(out)

def gen_pattern(pattern, n, seed):
    """四类预算模式: const_high / const_low / random / periodic"""
    rng = np.random.default_rng(seed)
    if pattern == 'const_high': return np.full(n, 80.0)
    if pattern == 'const_low':  return np.full(n, 15.0)
    if pattern == 'random':     return np.clip(50 + rng.normal(0, 15, n), 10, 90)
    if pattern == 'periodic':   return np.where((np.arange(n) % 100) < 20, 15.0, 70.0)
    raise ValueError(pattern)
