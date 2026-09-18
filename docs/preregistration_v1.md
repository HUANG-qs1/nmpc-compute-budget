# Preregistration v1.0 (Day 10, 定稿)

## 研究问题
算力预算波动下, ComputeBudgeter (L/M/H 档位调度) 相比固定档位基线,
能否在同等平均预算下显著降低跟踪误差?

## 假设 (confirmatory, 写死)
- H1 (主假设): 在 random/periodic 预算模式下, 调度器的 RMSE 比
  最优固定档位基线低 >= 8% (delta = +8% RMSE, 相对改善)
- H2 (次假设): 调度器 timeout_rate <= 固定高档基线的 1/2

## 指标纪律 (继承 v0, 不变)
- 主指标: 归一化迭代数 + timeout_rate (平台无关)
- 展示指标: wall-clock (标注平台)
- 依据: 单拍 iter-time 相关 r=-0.038, 触发预登记 fallback

## 实验设计 (confirmation 阶段, Day 11-24)
- 轨迹: circle + fig8 (exploration 已用, confirmation 沿用但换 seed 集)
- seeds: 30 个, 100-129 (与 exploration 的 0-14 完全不重叠)
- 预算模式: random, periodic (const 模式无调度价值, 仅作 sanity)
- 基线 (5 个, 写死):
  B1 固定 Np=5 (L档)  B2 固定 Np=10  B3 固定 Np=15 (M档)
  B4 固定 Np=20 (H档)  B5 朴素 reactive 降档 (超时后下一拍降一档, 无滞回)
- 被试: ComputeBudgeter (EWMA + 滞回 + 驻留 + 可行性前提 q0.9 < B_k)
- 档位: L=Np10, M=Np15, H=Np20 (Day 9 闭环证据修正)

## 分析计划 (写死)
- 主检验: 调度器 vs B1-B5 的 RMSE, paired across 30 seeds,
  Wilcoxon signed-rank, alpha=0.05, Holm 校正 5 重比较
- 预算公平性: 所有方法在同一预算序列上跑, 比较在等平均预算下进行
- 效应量: 中位数差 + 95% CI (bootstrap 1000 次)

## 已知局限 (主动声明)
- 单平台 (WSL2, 无 cpufreq), wall-clock 仅展示
- tol 不敏感已记录, 不作为调度旋钮 (escape clause)
- kappa 为对角保守先验
