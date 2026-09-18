# 预登记文档 v0（草稿，Day 10 升 v1 后冻结）

## 平台协议（D05 锁定）
- 机器: 固定一台消费级笔记本（WSL2 Ubuntu），全程不换机
- 线程锁定: OMP/OPENBLAS/MKL_NUM_THREADS=1（env/bench_protocol.sh）
- CPU 调频: WSL 无 cpufreq 接口，已如实记录（env/cpu_governor.txt）
- 计时方法: time.perf_counter 包裹求解调用

## 计时卫生学结论（D05 实测，可引用）
- 同配置 100 次: median=14.59ms, IQR/median=8.5% (<10%, PASS)
  （max=127ms 为首次调用预热离群点，佐证 WARMUP 必要性）
- 单拍迭代数—wall-clock 相关性: r=-0.038 (n=30, FAIL)
  结论: 单拍 wall-clock 被固定开销/抖动主导，迭代数不能代理单拍耗时；
  聚合层面（全程总迭代数 vs 总耗时）相关性待 Day 8 扫描数据再验。

## 指标口径（已按 D05 预案降级，一句话钉死）
- 主指标: 归一化迭代次数 ＋ 超时率（跨平台可复现）
- 辅助指标: wall-clock 中位数与分位数（仅作展示，不作为判定依据）
- 该降级已按 Day 5 预案触发，原因: 单拍相关性 r=-0.038 < 0.9

## 待 Day 10 定稿项
- δ 界值（RMSE 相对满配 +8% 或包络半径 5%，二选一写死）
- 30 个种子列表
- 五基线配置与探索/确认实验划分
