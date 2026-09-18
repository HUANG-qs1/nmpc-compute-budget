# Preregistration v1.1（2026-09-04，Day 23，解封 seeds 100–129 之前修订）

> 本版取代 v1.0（docs/preregistration_v1.md，Day 10 定稿，原文保留不删）。
> 全部修订发生于 confirmation seeds 100–129 解封之前（amend before unblinding）。
> 论文中必须原文申报以下四处修订及本修订记录。

## 修订记录（申报用）

### (a) H1 由优效改为非劣效（方向性修订）
- 原 H1（v1.0）：调度器 RMSE 比最优固定档位基线低 >= 8%（优效）。
- 新 H1（v1.1）：在可行性约束（timeout_rate ≤ 5%）下，v3 的关键工况 RMSE 相对最优可行基线的相对劣化 ≤ +8%。
- 动机：v1.0 的 H1 是 Day 10 的编码错误。当时探索数据（seeds 5–14）已显示调度器的 RMSE 优势来自"可行性筛选"而非逐拍精度；后续探索批（seeds 20–29）确认 v3 vs reactive RMSE 打平（<4%）。论文真正主张 = "精度追平 + 冻结/超时率数量级改善"，优效故事由 H2 承接。
- 非劣效界值 +8% 的依据：RMSE 差异 <8% 在本跟踪任务中不构成工程意义的差别——过渡带内相邻档位的 RMSE 变化为数量级（Np 5→15 时 circle 0.197→0.019），8% 远小于任何档位决策造成的效应，且小于 periodic 模式 seed 批间方差的 1/20。
- 可行性约束的理由：无可行性限定时，方法可靠高超时率（冻结输入）换取表观低 RMSE，比较对象不可比；timeout_rate ≤ 5% 同时约束被试与基线。
- 比较集：全部 5 个基线（fixed Np∈{5,10,15,20} + reactive），逐工况（模式×轨迹）取满足可行性约束者中 RMSE 最低者。若某工况无任何基线满足可行性约束，该工况不参与 H1 判定，单独报告。

### (b) periodic 模式必须报 per-seed 分布
- 依据：D16 发现 periodic fig8 timeout 存在 23 倍 seed 批间方差（commit 2fd7ab6）。仅报均值会掩盖相位敏感性。
- 执行：所有模式×轨迹组合均报 per-seed 分布（箱线图/散点），periodic 为强制项。

### (c) 被试定义 v1 → v3
- 新被试：ComputeBudgeter(dwell=1, use_freeze=False, online=True)，档位 L=Np10 / M=Np15 / H=Np20，门 = P² 在线 q90 估计 < 当拍预算。
- 依据：消融（D13–D18，commits 335cbab…8ef88b9）证明 dwell/freeze 为有害组件（负结果，写入论文讨论）；online 自标定与静态门在噪声内一致（D16, commit 2fd7ab6）且换机免标定。

### (d) 扰动实现确定性化
- 旧实现：get_random_disturbance 使用 numpy 全局随机态，扰动实现依赖进程内运行顺序；同 seed 下不同方法扰动不对齐；periodic 模式 30 个 seeds 的预算序列完全相同（gen_pattern 的 periodic 分支不使用 rng）。
- 新实现：每 seed 独立 rng（np.random.default_rng(seed)）预生成整条扰动序列，边际分布不变（amp·(−0.1+0.05·randn)）；同 seed 下 6 个方法面对完全相同的预算+扰动，配对严格成立，结果与运行顺序无关。
- 申报：探索批与 confirmation 批的扰动实现不同，两批不做直接数值对比。
- 回归验证：修复后重跑 seeds 30–31 v3-online（random × 2 轨迹），与 exp02 同 seed RMSE 差异 <20% 方可启动 confirmation（experiments/exp05_confirmation/regression_disturbance_v1.py）。

## 研究问题（不变）
算力预算波动下，ComputeBudgeter（L/M/H 档位调度）相比固定档位基线，能否在同等平均预算下保持跟踪精度并显著降低超时/冻结？

## 假设（confirmatory，v1.1 写死）
- H1（主假设，非劣效）：见修订 (a)。判定：逐工况，30 paired seeds，d_i = log(RMSE_v3,i / RMSE_bestfeas,i)；d_i 中位数的单侧 95% bootstrap CI 上界 < log(1.08) 判非劣效成立；敏感性分析用平移单侧 Wilcoxon signed-rank（d_i − log(1.08)，alternative = less）。多重性（Holm 一致置信水平）：4 个工况的非劣效检验按 Holm 排序，第 j 个排序假设使用置信水平 1−α/(m−j+1)（m=4, α=0.05）构造单侧 bootstrap CI；非劣效结论仅对通过 Holm 筛选的工况成立。唯一判据是（调整后置信水平的）CI 上界 vs 界值——"优效不显著"不得解释为"打平"。
- H2（次假设，优效，不变）：调度器 timeout_rate ≤ 固定高档基线（Np=20）的 1/2。paired Wilcoxon signed-rank，单侧，α=0.05。

## 指标纪律（继承 v0/v1.0，不变）
- 主指标：归一化迭代数 + timeout_rate（平台无关）；展示指标：wall-clock（标注平台）。
- 依据：单拍 iter-time 相关 r=-0.038，触发预登记 fallback。

## 实验设计（confirmation 阶段）
- 轨迹：circle + fig8；seeds：30 个，100–129（与 exploration 完全不重叠）。
- 预算模式：random、periodic；敌意 regime 组（2x 速参考 + amp=2.0 扰动，标准 Markov P 预算）用同 seeds 追加。
- 基线（5 个，不变）：B1 fixed Np=5，B2 fixed Np=10，B3 fixed Np=15，B4 fixed Np=20，B5 朴素 reactive（超时降一档、宽裕升一档、无滞回无驻留）。
- 被试：v3（见修订 c）。
- 预算公平性：所有方法在同一预算序列 + 同一扰动序列上跑（修订 d），比较在等平均预算下进行。

## 分析计划（v1.1 更新）
- H1/H2 判定：见"假设"节。
- 效应量：中位数差 + 95% CI（bootstrap 1000 次）。
- per-seed 分布：见修订 (b)。

## 已知局限（主动声明，v1.1 追加第 4 条）
- 单平台（WSL2，无 cpufreq），wall-clock 仅展示。
- tol 不敏感已记录，不作为调度旋钮（escape clause）。
- kappa 为对角保守先验。
- 探索批与 confirmation 批扰动实现不同（修订 d），两批不做直接数值对比。

---

## 修订 (f) — const_low 挽救实验（D32 晚，跑前注册）

**动机**：v5 标准化检验结局 C（n_trig=0）表明在 random/periodic/hostile 三种工况下，v3 可行性门已压制长冻结串，cur_phi 从未达阈 θ=0.5，触发器未被行使，v5 的有效性既未被证实也未被证伪。const_low（全程 15ms，永久饥饿）是理论预测触发器必然上场的工况：预算恒等于最低档 q90 之下，冻结串被迫拉长，cur_phi 必然累积超阈。

**设计**：与 run_v5_normalized_v1.py 完全同构（配对、标准化时间尺、seed 内共享 calib、v3 vs v5(θ=0.5)、dwell=1、use_freeze=False、online=True），唯一改动：budget pattern = const_low（np.full(n, 15.0)）。轨迹 circle + fig8，种子 100–129（确认种子），共 2 方法 × 2 轨迹 × 30 种子 = 120 runs。

**判定标准（跑前锁定，不看结果不改）**：

- **标准 0（有效性前提，sanity）**：v5 的 n_trig 中位数必须 ≥ 1（每条轨迹）。若触发器在 const_low 下仍不点火，实验无结论，v5 设计前提本身需检讨——此结果记为"结局 D：工况无法行使触发器"。
- **标准 1（主要）**：v5 TO_med < v3 TO_med，配对单侧 Wilcoxon（alternative='less'）p < 0.05，两条轨迹分别判定。
- **标准 2（安全性）**：RMSE 非劣，d_i = log(RMSE_v5/RMSE_v3)，单侧 bootstrap CI（B=10000）上界 < log(1.08)。

**结局分支**：
- A：标准 0 ✓ + 标准 1 ✓（至少一条轨迹）+ 标准 2 ✓ → v5 以"极端饥饿工况保命器"身份进论文（scoped claim，明确限定 const_low 类慢性饥饿工况）。
- B：标准 0 ✓ + 标准 1 ✗ → v5 触发但无收益，阴性结果坐实，写入论文作为门控设计充分性的证据。
- C：标准 0 ✓ + 标准 1 ✓ 但标准 2 ✗ → 触发有效但代价过大，需查 RMSE 分解后定夺。
- D：标准 0 ✗ → 见上。

**承诺**：无论结果方向如何，完整写入 d33 报告；不重跑、不换种子、不调 θ。

---

## 修订 (e) — 归一化时间尺（D30 决定，D34 补登记）

**状态声明（日期如实）**：本修订于 D30（2026-09-05，墙钟 regime 漂移确诊日）获学生书面同意（格式："同意修订(e)，无论结果方向如何"），同日晚实施并启动归一化确认批。证据：runner experiments/exp05_confirmation/run_confirmation_v3.py（CALIB_REF 首次引入 commit 9a82067，2026-09-06）、归一化批次 CSV（文件名日期 20260905/20260906）、d31 重判报告（docs/reports/d31_normalized_rejudge_v1.md）。**流程疏漏声明**：本修订当时未同步登记进本文档，属流程失误，于 D34（2026-09-06）补记；补记不改变"修订先于归一化批次"的事实顺序（批次文件名日期与 commit 链可查）。

**内容**：budget_eff = budget_nominal x (calib_run / CALIB_REF)，CALIB_REF = 25.0 ms（快 regime 下 Np15 基准求解中位耗时，D30 标定）。calib_run = 每个 run 开始前 3 次固定 Np15 求解（固定初态 [0,0,0]，circle 参考 seg[:15]）的中位数。超时判定与调度器输入（可行性门的 budget）一律使用 budget_eff；CSV 表头含 budget_scale = calib / CALIB_REF。

**动机**：D30 发现 WSL2/Windows 分钟至会话级墙钟速度漂移：同配置超时率跨会话 2-5 倍不可复现；同会话交错 A/B 证明 runner 等价；机器过夜变快（corr(run order, calib) = -0.36）。不追物理根因，以每 run 自标定的归一化尺替代名义墙钟（科学问题用定义解决）。

**验证与残余风险（跑后记录）**：交叉会话验证 |dTO| med 0.001、RMSE 比 1.000、scale 范围 0.72-1.48（跨会话验证集）。残余风险：knife-edge 配置批间摆动（periodic/fig8 TO_med 2.55% 与 5.45% 两批观察值），一律中位数+尾部双报告。D24 periodic/fig8 的 12% 判定正式撤回（regime 污染），撤回前数据归档降级，不作任何确认性用途。

---

## 修订 (g)：periodic/fig8 单元的机制定性与相位鲁棒性实验

登记日：2026-09-06（D35）。学生签字：2026-09-06，"同意修订（g)，无论结果方向如何"。

### g.1 背景与动机
确认实验（种子 100-129，已封存）H1 族 6 个条件单元 5 个通过 NI 判定；唯一未过为 periodic/fig8：v3 可行性限定未达标（TO_med=5.45%>5%），但该单元 RMSE 优势明显（d_med=-0.7700）。相关事实：① D16 观测到 periodic/fig8 超时的种子-相位敏感性（批间方差 23 倍）；② D34 数值确认 fig8 交叉口曲率约等于 0、最大曲率在瓣部（idx=629）。待答问题：该不可行是"周期算力模式与轨迹周期相位锁定致同批拍点反复挨饿"，还是相位无关的结构性饥饿。

### g.2 明文条款（叙事决策，先于实验锁定）
1. periodic/fig8 单元按修订 (a) 既定条款单独报告，不进 Holm 族（m=4 不变），其 RMSE 仅作描述性陈述。此条款不因 (g) 结果改变。
2. 已封存 H1/H2 主分析层（笔记本，种子 100-129）不被 (g) 触碰、不重判、不补跑。
3. (g) 为机制诊断实验，结果只进讨论/边界条件章节；即使某相位下 v3 恢复可行，也不回流修改 H1 结论，至多作为局限性与未来工作素材。

### g.3 实验设计
- 平台：服务器（阿里云 ecs.u2i 4vCPU/8GiB，华北6 乌兰察布）；开跑前须通过 24h calib 审计，不合格则暂停上报。
- 条件：pattern=periodic，traj=fig8；相位臂 phi_k=k/8*T_pat（k=0..7，T_pat 为周期模式周期）；phi=0 臂在服务器重跑，仅供本平台内对照，不与笔记本数据混池。
- 方法：v3（主体）+ reactive + fixed20（参照）。
- 种子：130-144（15 个，全新段位）。总 run 数=3x8x15=360。
- 附带插桩：逐拍求解时间记录，产出 run 内漂移诊断（验证归一化时间尺在服务器上的充分性），描述性，不立假设。

### g.4 分析计划（跑前冻结）
- 主指标：各相位臂 TO_med 与 RMSE（对 fixed20 配对差）。
- 判定一（相位敏感性）：跨相位 TO_med 极差 vs 种子噪声 bootstrap 95% CI（B=10000，percentile）；极差显著大于噪声则相位敏感成立。
- 判定二（可行性恢复）：任一相位臂 TO_med<=5% 则为"相位可缓解"；全不满足则为"结构性饥饿"。

### g.5 决策规则（与结果方向无关）
- 相位敏感成立：叙事为相位锁定边界条件，相位抖动（dithering）列为未来工作，本文不实现新机制。
- 结构性饥饿成立：叙事为周期算力下 fig8 硬性边界，结合逐拍饥饿分布图做失败模式分析。
- 两种结果均如实写入；分析代码与阈值跑前冻结。

## 修订 (h)：创新点二——完整版误差包络在线标定

登记日：2026-09-06（D35）。学生签字：2026-09-06，"同意修订（h)，无论结果方向如何"。

### h.1 定位
复活开题报告 4.6 完整版方案：对 v3 在算力饥饿事件下的跟踪误差构建具有覆盖率保证的条件误差包络（conformal 系），与理论线（C4 冻结串严重度律 e95 约等于 c+A*(L*phi_peak)）互相印证。

### h.2 组成（全部预登记，无缩减）
1. epsilon=0.05 抖动校准采集：校准运行在算力预算上施加 5% 随机抖动；
2. 分层分位数：按冻结串长度 L 分箱 x 参考点曲率 kappa 分箱估计条件分位数；
3. 滚动校准：滑动窗口重标定应对分布漂移；
4. 重要性权重对照：校准/验证集协变量偏移下加权 conformal vs 不加权；
5. ACI：滚动窗口（200 拍）经验覆盖率偏离名义 90% 超 5pp（<85% 或 >95%）即激活，步长 gamma=0.01 跑前冻结。

### h.3 实验设计
- 平台：同 (g)，先过 24h calib 审计。
- 条件网格：2 traj x 3 pattern（random/periodic/hostile）。
- 种子：校准 160-189，验证 190-219，互斥全新。
- Run 数：校准 180 + 验证 180 = 360。
- 逐拍插桩字段（跑前冻结）：timestamp、solve_ms、timed_out、gear、Np、当前档位 q90 估计、冻结串长度 L、参考点曲率 kappa、路径进度 s；同供 P2 陈旧性与档位切换率描述性分析。

### h.4 分析计划（跑前冻结）
- 名义覆盖率 90%。主比较：分层+滚动 (iii) vs 边际 split-conformal (i)；(ii) 分层单独、(iv) 加重要性权重、(v) 加 ACI 为消融层。
- 主终点：验证种子经验覆盖率落在 [85%,95%] 且平均宽度窄于 (i)。
- 报告层级 (i) 到 (v) 跑前冻结，禁止跑后挑指标挑变体。

### h.5 决策规则（与结果方向无关）
- 各变体达标与否按层级如实报告；全不达标则写失败分析（分布漂移、饥饿事件稀疏性），本身为可发表内容。
- (h) 与 H1/H2 完全解耦：不改主结论、不混池、不进 Holm 族。

### h.6 平台声明
(g)(h) 全部新数据产生于服务器；笔记本数据封存不动；两平台数据永不混池，论文中分别标注采集平台。

## 治理记录（D35，2026-09-06）
学生授权：核心不偏离前提下实验设计由指导方主导；若实验效果不佳，优先深挖创新点（深度优先于广度）。既有纪律不变：任何新实验设计仍在跑前书面登记，签字后冻结。

## 修订 (i)：MuJoCo 嫁接验证（graftability validation，标准版）— 2026-09-08 学生签字

i.0 定位：不引入新假设族，不改变 H1/H2 封存结论统计地位；外部效度验证章。判定阈值预冻结于 i.6，无论结果方向如何不改判定逻辑。
i.1 科学问题：预算机制（可行性门 + P2 在线分位数闸 + 归一化时间尺）是 WMR 特例还是可嫁接通用件？判据=序关系保持，非绝对数值复现。
i.2 平台：MuJoCo 3.12 四旋翼（刚体动力学+电机一阶滞后）；控制栈与 WMR 完全一致（CasADi/IPOPT NMPC，同一 ComputeBudgeter v3, dwell=1, use_freeze=False, online=True）。只换 plant，不换 controller/budgeter。
i.3 任务集：hover 定点、step 阶跃、3D circle 跟踪、3D fig8 跟踪。
i.4 失配隔离控制臂：名义臂（模型=真值）+ 失配臂（质量/惯量 +20% 固定偏移）。失败归因用：budgeter 失效 vs 模型失配，两者可分离。
i.5 设计：3 方法（v3/reactive/fixed20）x 3 模式（random/periodic/burst）x 4 任务 x 15 seeds（230-244，本修订登记启用，与 100-219 无重叠）x 2 失配臂 = 1080 runs。冒烟只用 seed 95。标定沿用修订(e)：每 run 3 次固定 Np15 求解取中位，CALIB_REF=25.0ms。
i.6 预冻结判定：主指标 cell 级 TO_med，辅指标 RMSE_med。GRAFT-OK：9 个主对比 cell 中 >=8 个满足 TO(v3)<=TO(reactive)<=TO(fixed20) 且 >=8 个满足 RMSE(v3)<=RMSE(fixed20)。PARTIAL-GRAFT：序关系 5-7 个 cell 成立，失配臂归因。GRAFT-FAIL：<=4 个，通用性主张收缩至轮式平台，如实报告。不设新 NHST 族；效应量 + bootstrap 95% CI（B=10000, seed 20260907）。全量种子进统计，禁 cherry-picking；插图可选代表 seed，选择规则须写明。
i.7 运行纪律：服务器独占、nohup 夜批、方法臂交错、无并发 timing 实验；批前冒烟（seed 95）与笔记本数值核验。
i.8 论文作用：独立 graftability 章，MuJoCo 渲染图（OSMesa 无头）+ matplotlib 定量图；与 C4 严重度律、修订(h) 共形包络三角互证（深度缝合节）。
参数说明：seeds 230-244 接 (h) 之 190-219 后，池不重叠；失配 +20% 为文献常规档，足激发失配效应且不至全域不可行。

## 修订 (i.5) 补丁：四旋翼预算制度档位锚定 — 2026-09-08 学生签字

背景：冒烟（seed 95，探索池）显示四旋翼 Np15 标定 269ms，为 WMR 约 10 倍；原制度（15-70ms）经标尺放大 10.76 倍后全程高于实际求解耗时，预算无约束力，嫁接验证将空洞化。
补丁内容：nominal 预算 = WMR 制度数值 x kappa，kappa = q90_quad(Np15)/27.0；CALIB_REF_quad = q90_quad(Np15)。q90_quad 由档位扫描实测（探索种子 90-99，合法池，先于任何正式 run）。标尺机制、i.6 判定阈值、种子池 230-244 全部不变。WMR 封存结论不受影响（同平台 CALIB_REF 仍为 25.0）。
性质声明：档位锚定是修订(e)归一化时间尺的跨平台推广——标尺单位即「本平台 Np15 标定」的倍数；kappa 来源于探索池标定数据，非正式实验结果数据，不构成数据驱动改设计。

---

## 修订（i.7）：求解器硬deadline、发散删失判据、恢复窗口预言登记

签署：黄清苏，2026-09-08 夜（书面同意原文："同意修订（i.7)，无论结果方向如何"）

背景：exp07 全量批次（srv1）运行至第 9 run 时发现 doom-loop 自放大：失稳后 IPOPT 迭代数由标定值 4-7 膨胀至 54-116，单拍墙钟由约 0.1s 膨胀至 0.7-5.4s，driver 自报 ETA 约 30 天，物理不可行。同期确认 budget_mean（213-289ms）高于各档 q90（92-163ms），预算制度尺度符合修订（i.5），非制度性错误；根因为求解器墙钟无上限。本修订经双方讨论确认非结果方向驱动：无论后续数据方向如何均执行。

(i.7a) 求解器硬 deadline：IPOPT 增加 max_cpu_time，取值为该 run 预算序列最大值 budget_max（i.5 归一化后的 budget_eff 序列）。逐拍语义不变性论证：任意拍若求解可在 budget_eff 内完成则正常返回（budget_eff <= budget_max，不受 cap 影响）；若求解超过 budget_eff，无论是否触发 cap，结果均为超时、保持上一控制。故控制序列与 timeout 标记同无 cap 版本逐拍等价，唯一差异为墙钟消耗。计时列（time_q50 等）语义因此变化：srv1 已产出 16 行全部作废存档（superseded_ 前缀），永不分析，不与新数据混池。

(i.7b) 发散删失判据：单 run max_err > 100 m（任务尺度 1.5 m 的 60 倍以上）判为 diverged-censored。删失 run 单独报告发散率、timeout_rate、safety_rate，不进入受控性能（RMSE、e95）统计；存活判定 = 非 diverged。阈值自本签署起冻结，禁止后续调整。

(i.7c) 预言登记（先于 periodic/burst 任何数据产生）：
  P1（恢复窗口）：periodic 与 burst 模式下，v3 在 circle 与 fig8 任务上的发散率 <= 20%，且显著低于 random 模式（预期约 100%）。
  P2（机制归因）：发散 run 的 iter_mean 系统性高于存活 run（预期 >= 5 倍），而 budget_mean 在发散/存活组间无系统性差异；即发散由求解时间的状态依赖膨胀驱动，而非预算严苛驱动。
  P3（包络包含序）：全矩阵存活 cell 数排序 v3 >= fixed20 >= reactive，且 v3 严格多于 fixed20。
  若 P1 被否，则于模块四分析阶段重开期刊目标与降级议题（双方签字制），此前不议。

(i.7d) v4 种子封存：srv1 数据显示 v3 在 circle/random 下 gearL 占比 0.990，提示在线 P2 分位数在 doom 开始后被污染、门控锁死低档。分位数污染防护（v4）封存为 future work，本文不实施。

(i.7e) 不变量：预算制度（patterns、生成参数、KAPPA=6.052、CALIB_REF=285.0）、种子集合 230-244、任务集、失配臂、ComputeBudgeter 逻辑一律不动；本修订仅改变求解器墙钟上限、新增删失判据与预言登记。

### 修订(i.9)：exp08 burst 连续稀缺长度扫描（生存悬崖判据验证）2026-09-11

**背景**：exp07 全矩阵判决（verdicts_exp07_srv2.txt）：P1 FAIL(62.5%)，P2 FAIL(4.5x<5x，协变量混淆排除：175.5 vs 174.5ms)，P3 PASS(41.4% < 80.6% ≤ 81.7%)。run 级 iter_mean 稀释假设获分层探索支持（deep 21.2 vs shallow 14.2），逐拍机制证据移交 exp08 与代表性 dump。

**设计**：
- 供给：burst 模式，blen ∈ {5,10,15,20,30} 拍（0.5-3.0s）；base=70ms、low=15ms、p_start=0.0067，与 exp07 冻结参数一致；同一 seed 下各 blen 档 burst 起始时刻由同一随机流生成，仅持续时长不同（剂量递增对照）
- 矩阵：4 任务 × {v3, fixed20} × 5 档 blen × 15 种子 = 600 runs；mm 固定 0.0
- 种子：注册块 330-344（与 exp07 230-244、封存 100-129、探索 0-99 不交叠）；smoke 只用 95
- 代码：exp08 经 import 复用 exp07 冻结的 run_one/task_ref/calibrate；exp07 文件零改动

**预言登记**：
- P4（剂量-悬崖）：v3 各任务发散率沿 blen 单调不减；circle+fig8 合并发散率在 blen=15 ≥ 40%
- P5（边界移动）：circle、fig8 各自的 L50(v3) > L50(fixed20)（L50 = 合并发散率首超 50% 的最小 blen）；hover、step 在 blen=30 处 div(v3) < div(fixed20)
- P6（机制修正版）：v3 发散 run 的 iter_mean 组均值沿 blen 单调不减

**判决与统计纪律**：同 (i.7)；发散判据 (i.7b) max_err>100；统计一律基于全量 15 种子；收工验收三铁律（DRIVER ALL DONE / 601 行 / rc 非零计数为 0）通过前不做任何分析。

**不变量**：KAPPA=6.052；CALIB_REF=285.0；DT=0.1，TOTAL=100s；ComputeBudgeter 不动；exp07 数据与代码冻结。

签字：黄清苏 2026-09-11 "同意修订(i.9)，无论结果方向如何"
