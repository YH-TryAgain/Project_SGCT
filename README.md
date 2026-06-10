# SGCT RFID Anti-Collision Simulation Project

本项目用于实现、复现和对比 RFID 标签防碰撞算法，重点支持本文算法
`SGCT` 与典型树型、查询树型、分组型算法在统一仿真框架下的公平比较。

当前算法主线定位为 **Signature-Guided Collision Tree (SGCT)**，即“签名引导碰撞树协议”。
实验重点围绕签名分组、局部短 ID、后缀扩展、低维回退、稀疏签名宽度和资源队列成本展开。

当前项目已经加入 paired-seed 正式实验管线：在同一个实验点、同一个
`run_id` 下，所有算法使用完全相同的一批标签 ID，从而避免“每个算法各自随机
生成场景”带来的比较偏差。

## 正式复现入口

论文正式实验只以 `formal_experiment.py` 为准；`Exp1.py` 到 `exp6.py` 是历史实验脚本，
保留用于追溯，不建议再作为论文数据来源。正式结果默认保存到 `results_paper_final/`。

正式对比中的 `DRCT` 由 `DRCTFinalAlgorithm` 实现；历史文件 `DRCT.py`、
`DRCT_strict.py` 仅用于兼容测试和复现过程追溯。

最常用的复现命令如下：

```bash
python formal_experiment.py --experiment formal_experiment10_algorithm_comparison --runs 50 --processes 1 --resume-existing
python formal_experiment.py --experiment formal_experiment13_sgct_signature_grouping --runs 50 --processes 1 --resume-existing
python formal_experiment.py --experiment formal_sgct_ber_robustness --runs 50 --processes 1 --resume-existing
python formal_experiment.py --paper-only --runs 50 --processes 1 --resume-existing
python generate_paper_tables.py
pytest -q
```

正式论文表格由 `generate_paper_tables.py` 从现有 CSV 自动生成，避免手工复制造成口径不一致。
paired bootstrap 置信区间可单独用 `compute_paper_ci.py` 计算。
`generate_paper_tables.py` 同时输出长格式统计表和可直接粘贴到论文中的
`paper_table_*_compact.csv`；其中 `Gamma_B` 的论文口径为
`gamma_B_aggregate = mean(throughput_tags_per_sec) / mean(avg_total_bits)`。

## 目录结构

```text
Project_SGCT/
├── Framework.py                 # 仿真核心、Tag、时延/能耗计算、场景生成
├── Tool.py                      # 结果汇总、派生指标、CSV 输出和绘图
├── algorithm_base_config.py     # 算法注册表和默认对比算法列表
├── formal_experiment.py         # paired-seed 正式实验入口
├── generate_paper_tables.py      # 从正式结果自动生成论文表格
├── compute_paper_ci.py           # paired CI 与 bootstrap CI 计算
├── FORMAL_EXPERIMENTS.md        # 正式实验协议说明
├── OCG_HLCT_PB.py               # 本文算法 SGCT
├── OCG_HLCT.py                  # 旧版内部基线
├── DRCT.py                      # DRCT 复现
├── LAPCT.py                     # LAPCT
├── NLHQT.py                     # NLHQT
├── DQTA.py                      # DQTA
├── EMDT.py                      # EMDT
├── EAQ_CBB.py                   # EAQ-CBB
├── HT_EEAC.py                   # HT-EEAC
├── FHS_RAC.py                   # FHS-RAC
├── ICT.py                       # ICT
├── Exp1.py ... exp6.py          # 旧版实验脚本
├── tests/                       # 单元测试与算法 smoke tests
└── results/                     # 实验输出目录
```

## 环境准备

建议使用 Python 3.10 或更高版本。

```bash
pip install -r requirements.txt
```

在 Windows PowerShell 中进入项目目录：

```powershell
cd d:\Administrator\Documents\论文\RFID\Exp\Project_SGCT
```

## 当前默认对比算法

默认正式对比算法来自 `algorithm_base_config.py` 的 `ALGORITHMS_TO_TEST`：

```text
SGCT
DRCT
NLHQT(n=2)
LAPCT
DQTA(k_max=3)
EMDT
EAQ_CBB
HT_EEAC
```

其中 SGCT 作为独立算法主线；旧内部算法只用于历史对照和消融解释。

## 正式实验设计

推荐使用 `formal_experiment.py`，而不是旧版 `Exp1.py` 到 `exp6.py`。
正式实验的关键设计如下：

- 对每个 `(实验名, 参数值, run_id)` 生成一次标签集合。
- 同一实验点的所有算法复用完全相同的 `tag_ids`。
- 每次运行记录 `point_seed` 和 `algorithm_seed`，便于复现。
- 保存 run-level 原始数据、seed 清单、95% 置信区间和传统 KPI 透视表。

内置正式实验包括：

```text
formal_main_scalability_uniform
formal_id_length_sweep
formal_distribution_robustness
formal_common_prefix_sweep
formal_inspect_window_sensitivity
formal_fcw_window_sensitivity
formal_ovg_stress_ablation
formal_check_gating_ablation
formal_full_algorithm_comparison
formal_experiment10_algorithm_comparison
formal_experiment11_hlct_improvement
formal_experiment13_sgct_signature_grouping
formal_sgct_scalability
formal_sgct_prefix_sweep
formal_sgct_signature_sensitivity
formal_sgct_ber_robustness
formal_sgct_id_length_structured
formal_sgct_energy_sensitivity
formal_sequential_scalability
formal_ocg_ablation
```

完整说明见 `FORMAL_EXPERIMENTS.md`。

## 运行实验

### 快速试运行

只比较 `SGCT` 和 `DRCT`，每个点运行 5 次：

```bash
python formal_experiment.py --experiment formal_main_scalability_uniform --runs 5 --algorithm SGCT --algorithm DRCT
```

### 论文级正式主实验

每个实验点运行 50 次 paired runs。默认只开 1 个进程，避免长实验占满 CPU；
中断后可用 `--resume-existing` 从已保存结果继续。

```bash
python formal_experiment.py --paper-only --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

`--paper-only` 只运行五个 SGCT 论文正式实验：

```text
formal_experiment10_algorithm_comparison
formal_sgct_scalability
formal_sgct_prefix_sweep
formal_experiment13_sgct_signature_grouping
formal_sgct_ber_robustness
```

表格来源固定为：

```text
Table III <- results_paper_final/formal_experiment10_algorithm_comparison/
Table IV  <- results_paper_final/formal_experiment10_algorithm_comparison/
Table V   <- results_paper_final/formal_experiment13_sgct_signature_grouping/
Table VI  <- results_paper_final/formal_experiment13_sgct_signature_grouping/
Table VII <- results_paper_final/formal_sgct_ber_robustness/
```

### SGCT 消融实验

```bash
python formal_experiment.py --experiment formal_experiment13_sgct_signature_grouping --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

消融版本包括：

```text
SGCT
SGCT(no_signature_grouping)
SGCT(no_local_short_id)
SGCT(no_suffix_extension)
SGCT(no_low_d_fallback)
SGCT(d4)
SGCT(d6)
SGCT(d8)
SGCT(d10)
```

实验输出会保存 run-level 数据、95% 置信区间、显著性检验、KPI 表和图像文件；
图像生成时不会弹出窗口。

### SGCT 补充实验

```bash
python formal_experiment.py --experiment formal_sgct_ber_robustness --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
python formal_experiment.py --experiment formal_sgct_id_length_structured --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
python formal_experiment.py --experiment formal_sgct_energy_sensitivity --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

资源/队列成本实验 `formal_sgct_resource_queue_cost` 从现有正式结果抽取，
不重新仿真，统计 `peak_stack_depth`、`total_steps`、`total_slots`、
验证次数和 SG 诊断计数等指标。

### 公共前缀扫描实验

该实验用于验证 OVG 是否在 batch EPC / 长公共前缀场景中发挥作用：

```bash
python formal_experiment.py --experiment formal_common_prefix_sweep --runs 100
```

默认扫描：

```text
prefix_length = 0, 16, 32, 48, 64, 72, 80
TOTAL_TAGS = 1000, 2000, 5000, 10000
BINARY_LENGTH = 96
id_distribution = prefixed
```

注意：旧方案中的 `prefix_length=88` 对 `TOTAL_TAGS=5000, BINARY_LENGTH=96` 不可行，
因为后缀只有 8 bit，最多只能生成 256 个唯一 ID。正式实验已改为：

框架现在会在不可行配置下直接抛出 `ValueError`，避免实验无限等待。

### Inspect Window 敏感性实验

该实验用于验证有限窗口 Inspect 的取值是否合理：

```bash
python formal_experiment.py --experiment formal_inspect_window_sensitivity --runs 50 --algorithm HLCT-Base
```

默认扫描：

```text
inspect_window_bits = 4, 8, 16, 24, 32, 96
TOTAL_TAGS = 5000
BINARY_LENGTH = 96
id_distribution = prefixed
prefix_length = 64
```

### FCW Window 敏感性实验

该实验用于验证 `fused_window_bits=4` 的默认值是否合理：

```bash
python formal_experiment.py --experiment formal_fcw_window_sensitivity --runs 50 --algorithm HLCT-Base --processes 1
```

默认扫描：

```text
fused_window_bits = 0, 2, 4, 6, 8, 12, 16
scenario_label = random, prefixed, prefix64, prefix72, prefix80, dispersed, sequential, clustered
TOTAL_TAGS = 5000
BINARY_LENGTH = 96
```

其中 `fused_window_bits=0` 等价于无融合窗口；`prefix64/72/80` 表示对应公共前缀
长度的 prefixed 场景，`clustered` 表示多批次公共前缀 EPC。该实验关闭
`enable_adaptive_fcw`，以便纯粹观察窗口长度本身的收益和开销。

### OVG Stress 消融实验

该实验专门验证 OVG 在困难偏斜场景中的独立贡献：

```bash
python formal_experiment.py --experiment formal_ovg_stress_ablation --runs 100 --processes 1
```

默认场景：

```text
scenario_label = prefix64, prefix72, prefix80, dispersed, clustered
TOTAL_TAGS = 5000
BINARY_LENGTH = 96
```

重点观察 `p95`、`fallback_invocation_ratio`、`peak_stack_depth`、
`ovg_trigger_count`、`total_bits` 和 `avg_tag_bits`，避免只看平均时间。

### Check-Gating / FCW 正式消融

该实验用于正式证明 FCW 与 Check-Gated EPC Verification 的贡献：

```bash
python formal_experiment.py --experiment formal_check_gating_ablation --runs 100 --processes 1
```

默认比较 full、`no_fused_check`、`no_check_gating`、`fixed_8bit_check`、
`no_check_escalation`、`no_ovg`、`no_prefix_stagnation`、`lock_only` 和
`cbit_only`。

### 完整算法对比实验

该实验把扩展后的基线算法放在同一 paired-seed 入口下比较：

```bash
python formal_experiment.py --experiment formal_full_algorithm_comparison --runs 100
```

默认场景：

```text
scenario_label = random, prefixed, prefix64, prefix72, prefix80, dispersed, sequential, clustered
TOTAL_TAGS = 5000
BINARY_LENGTH = 96
```

默认算法来自 `ALGORITHMS_TO_TEST`，包括 HLCT-Base、DRCT、NLHQT、LAPCT、
DQTA、EMDT、EAQ-CBB、HT-EEAC、FHS-RAC、ICT、
SD-CGQT 和 SUBF-CGDFSA。

### 实验10指定算法对比

该实验严格使用你指定的论文主对比集合：

```bash
python formal_experiment.py --experiment formal_experiment10_algorithm_comparison --runs 100 --processes 1
```

默认算法：

```text
HLCT-Base
DRCT
LAPCT
DQTA(k_max=3)
EMDT
NLHQT(n=2)
```

默认场景仍覆盖：

```text
scenario_label = random, prefixed, prefix64, prefix72, prefix80, dispersed, sequential, clustered
TOTAL_TAGS = 5000
BINARY_LENGTH = 96
```

## 实验9完善内容

实验9后，`OCG_HLCT.py` 增加了更可观测的 OVG 触发与恢复机制：

- `prefix_stag_score`：累计“公共前缀几乎不增长、无 singleton、少数碰撞子组伴随大量 idle”等可观测信号。
- `repeated_collision_pattern_count`：记录重复碰撞签名 `(首碰撞位, 连续碰撞长度, 碰撞子组数, idle 子组数)`。
- OVG 触发不再只看单次 prefix stagnation，也会记录 score trigger 和 repeated-pattern trigger。
- OVG 后若没有 singleton，会继续 rehash/调整 `r_h`，并输出 `ovg_fallback_avoid_count`、`ovg_success_count`、`post_ovg_singleton_count` 等指标。
- 正式摘要会输出 `prefix_stag_score_trigger_count`、`repeated_pattern_trigger_count` 等 OVG 诊断指标。

轻量 smoke 对比已保存到 `experiment9_smoke_comparison.csv`。在 256 标签、3 个 paired runs
下，新默认 `5/10` Check 配置相对旧 `4/8` 的平均识别时间变化为：

```text
random:    336.625 ms -> 334.356 ms
prefix80:  446.573 ms -> 443.400 ms
clustered: 429.740 ms -> 428.755 ms
dispersed: 537.887 ms -> 531.825 ms
```

需要注意：`dispersed` 场景下 `HLCT-Base(no_ovg)` 仍比完整 OVG 路径更快
（520.775 ms vs 531.825 ms），因此论文中应把 OVG 定位为长前缀/偏斜恢复模块，
并通过 `formal_ovg_stress_ablation` 报告其收益边界，而不是宣称所有分布下都优于关闭 OVG。

## 实验10完善内容

实验10后，项目进一步完善了两类内容：

- `OCG_HLCT.py` 支持节点级 Adaptive FCW：节点可根据 OVG、prefix-stag、repeated-pattern、verify-fail 等可观测风险信号升窗，也可在 idle-rich 反馈下降窗。
- 实测 smoke 显示，Adaptive FCW 在当前仿真参数下作为默认项会轻微增加 total bits 和平均时间，因此正式默认保持 `enable_adaptive_fcw=False`，保留该机制用于消融和困难场景扩展。
- 默认 Check 参数改为 `f_default=5, f_escalated=8`。在 `random/prefixed/prefix80/dispersed/clustered` 五类 256 标签、5 次 paired runs 的 smoke 中，该配置的平均时间略优于旧 `4/8`。
- 修复 `NLHQT(n=2)` 在 short-ID 剩余位数小于 `n_way` 时可能空转到 `max_steps` 的问题；`formal_experiment10_algorithm_comparison` 的 5000 标签、1-run smoke 已能完整跑完。

实验10 smoke 结果保存在：

```text
experiment10_smoke_comparison.csv
results/formal_experiment10_algorithm_comparison/
```

## 实验11完善内容

实验11后，默认 OVG retry 预算从 `R_OVG=2` 调整为 `R_OVG=1`。原因是 paired smoke
显示，OVG 作为偏斜恢复模块有收益，但多次默认 retry 会拉长 dispersed / prefix
类场景的平均时间。新的策略是：默认只给 OVG 一次恢复机会，保留 rehash / adaptive
`r_h` 代码路径用于消融和高风险扩展，但避免让 OVG 变成常规长路径。

新增实验：

```bash
python formal_experiment.py --experiment formal_experiment11_hlct_improvement --runs 100 --processes 1
```

默认比较：

```text
HLCT-Base
HLCT-Base(prev_R2)
HLCT-Base(no_ovg)
HLCT-Base(adaptive_fcw)
HLCT-Base(no_prefix_stagnation)
```

实验11 smoke 结果保存在 `experiment11_smoke_comparison.csv`。在
`random/prefixed/prefix80/dispersed/clustered` 五类 256 标签、5 次 paired runs
下，平均识别时间为：

```text
HLCT-Base:                  419.288 ms
HLCT-Base(adaptive_fcw):    419.607 ms
HLCT-Base(prev_R2):         422.378 ms
HLCT-Base(prev_4_8_R2):     423.681 ms
HLCT-Base(no_ovg):          428.568 ms
```

因此当前默认相对 `prev_R2` 提升约 0.73%，相对 `prev_4_8_R2` 提升约 1.04%。
同时，`no_ovg` 明显更慢，说明 OVG 保留是必要的；但 Adaptive FCW 在当前时延/bit
模型下仍略慢，所以继续作为可选消融项而不是默认项。

## 实验12完善内容

根据 `实验12.md`，当前 HLCT-Base 增加了两项默认启用的反馈驱动优化：

- Guarded Adaptive CBIT Width：在干净的密集连续碰撞路径上允许 `CBIT r=4`；
  若节点已有 skew、no-progress、verification-fail、OVG retry、prefix-stagnation
  或 repeated-pattern 反馈，则保守退回 `r=3`。
- Multi-bit Fallback：fallback 不再固定只按第一个碰撞位二分；当可观测碰撞位足够时，
  默认使用 2 个碰撞位分组，以缩短 fallback 长路径。

新增实验：

```bash
python formal_experiment.py --experiment formal_experiment12_hlct_feedback --runs 100 --processes 1
```

默认比较：

```text
HLCT-Base
HLCT-Base(no_adaptive_cbit)
HLCT-Base(no_multibit_fallback)
HLCT-Base(prev_R2)
HLCT-Base(no_ovg)
HLCT-Base(adaptive_fcw)
```

3-run paired smoke 已写入 `results/formal_experiment12_hlct_feedback/`。相对
`HLCT-Base(no_adaptive_cbit)`，当前默认在 7 类场景上的平均时间下降约 `3.45%`，
总 bit 下降约 `4.90%`，碰撞槽下降约 `10.77%`；相对
`HLCT-Base(no_multibit_fallback)`，clustered 场景时间下降约 `8.60%`，说明
multi-bit fallback 修复了 ACBW 在簇状场景中引入的 fallback 长路径问题。

## 输出文件

每组实验输出到：

```text
results/<experiment_name>/
```

关键文件：

```text
raw_runs.csv                  # 每次运行的完整记录
run_manifest.csv              # seed、run_id、算法名和参数点
summary_ci95.csv              # mean/std/p95/95% CI
total_protocol_time_ms.csv    # 总识别时间
throughput_tags_per_sec.csv   # 吞吐率
system_efficiency.csv         # 系统效率
collision_slots.csv           # 碰撞槽数量
idle_slots.csv                # 空闲槽数量
total_energy_uj.csv           # 总能耗
total_bits.csv                # 总通信 bit
avg_tag_bits.csv              # 平均每标签发送 bit
avg_reader_bits.csv           # 平均每标签 reader bit
avg_total_bits.csv            # 平均每标签总通信 bit
```

启用 HLCT-Base 资源监控后，`summary_ci95.csv` 还会包含：

```text
inspect_collision_count       # 独立 Inspect collision 次数
fcw_cache_created_count       # FCW 缓存创建次数
fcw_cache_hit_count           # FCW 缓存命中次数
fcw_cache_hit_ratio           # FCW 缓存命中率
```

## 公共前缀 smoke 结果

还运行了一个小规模公共前缀扫描：

```text
实验名: formal_common_prefix_smoke_after_fix
标签数: 256
ID 长度: 96 bit
prefix_length: 0, 32, 64, 80, 88
重复次数: 每个点 2 次
输出目录: results/formal_common_prefix_smoke_after_fix/
```

HLCT-Base 的平均 OVG 触发次数：

| prefix_length | OVG trigger count |
|---:|---:|
| 0 | 0.0 |
| 32 | 4.5 |
| 64 | 4.5 |
| 80 | 8.0 |
| 88 | 0.0 |

这个 smoke 结果说明：OVG 不再是“纸面模块”，在中高公共前缀偏斜场景中已经能够被正常路径触发。`prefix_length=88` 的后缀空间很短，场景更接近小后缀顺序识别，因此没有触发 OVG。

## 已根据实验审计修正的问题

- OVG 触发：从弱触发改为基于本轮分裂统计的显式触发，唯一碰撞子节点会被提升为 `mode_hint="OVG"`。
- OVG 优先级：`mode_hint="OVG"` 优先于 no-progress fallback，避免还未执行 OVG 就被 fallback 抢走。
- OVG-direct：带有 `mode_hint="OVG"` 的碰撞节点会直接进入哈希虚拟分组，不再先支付一次 collision-bit Inspect 响应成本。
- OVG rehash-before-fallback：OVG 后的偏斜碰撞子节点会优先更换 seed / 保持 OVG，而不是过早进入 fallback。
- no-progress：不再把普通 collision child 都视为无进展，只在无成功且出现单碰撞多空闲或全碰撞时累加。
- Inspect 成本：新增 `inspect_window_bits=16`，碰撞位探测只请求有限窗口，而不是每个碰撞节点都读取完整剩余 EPC。
- OVG 场景门槛：新增 `ovg_min_prefix_bits=16`，避免均匀随机场景过度触发 OVG。
- 消融定义：`no_check_escalation` 改为固定 4-bit Check，即 `f_default=4, f_escalated=4`。
- 消融补充：新增真正的 `no_check_gating`，用于对比短 Check 与直接 EPC 响应。
- 正式实验：新增 `formal_common_prefix_sweep`，用于专门验证公共前缀长度对 OVG 的影响。
- 正式实验：新增 `formal_inspect_window_sensitivity`，用于验证 `inspect_window_bits=16` 的合理性。
- 场景生成：对 `prefixed` 分布增加唯一 ID 容量检查，避免 `prefix_length=88,N=5000` 这类配置卡死。
- 时间模型：`AlgorithmStepResult` 支持 `response_windows_bits=[...]`，多响应子周期可以逐一计入 T1/T2/tag window；LAPCT 的 4-way 聚合 step 已接入该模型。
- 通信复杂度：正式输出新增 `total_bits` 和 `avg_total_bits`，`summary_ci95.csv` 新增 `p95`。

仍需继续审计的问题：当前框架已经支持 `response_windows_bits`，HLCT-Base 的逐子组 step 和 LAPCT 的 4-way 聚合 step 已接入；后续投稿前还应逐一检查 DQTA、EMDT、NLHQT 等 baseline 是否存在类似“多个响应子周期合并成一个时间窗口”的情况。

## 实验2审计后的 smoke 结果

新增 `no_check_gating` 后的小规模消融 smoke：

```text
实验名: formal_ocg_ablation_smoke_exp2
标签数: 64
ID 长度: 32 bit
分布: prefixed
```

平均 tag bits/tag：

| 版本 | tag bits/tag |
|---|---:|
| HLCT-Base | 78.47 |
| HLCT-Base(no_check_escalation) | 78.47 |
| HLCT-Base(no_check_gating) | 132.02 |

这说明短 Check-Gated Response 在该 smoke 场景中确实降低了标签响应 bit。

Inspect window smoke：

```text
实验名: formal_inspect_window_sensitivity_smoke_exp2
标签数: 64
ID 长度: 32 bit
分布: prefixed
prefix_length: 16
```

| inspect_window_bits | time ms | tag bits/tag |
|---:|---:|---:|
| 4 | 83.21 | 56.13 |
| 8 | 83.88 | 66.81 |
| 16 | 84.34 | 80.78 |
| 32 | 84.34 | 80.78 |

这个 smoke 只用于验证实验链路，不作为论文结论；正式结论需要 50-100 paired runs。

## 实验3优化后的性能 smoke

根据 `实验3.md` 的建议，已加入 OVG-direct、OVG rehash-before-fallback、
更严格的 no-progress 判断，并保留 CBIT 对 sequential 场景友好的连续位快速分裂。

同口径对比 `formal_quick_comparison_after_fix` 与 `formal_quick_comparison_exp3`：

| 场景 | 时间变化 | tag bits 变化 | 说明 |
|---|---:|---:|---|
| dispersed | ↓ 12.33% | ↓ 6.57% | OVG-direct 和减少 fallback 带来明确收益 |
| prefixed | ↑ 0.84% | ↓ 0.82% | 基本持平，bit 略降 |
| random | ↑ 2.61% | ↓ 1.99% | OVG 不再误触发，但调度仍略慢于上一版 |
| sequential | 0.00% | 0.00% | 保留 CBIT 连续位路径后未再退化 |

修复后 HLCT-Base 相比 DRCT：

| 场景 | 时间优势 | tag bits 优势 |
|---|---:|---:|
| dispersed | 51.6% 更快 | 49.8% 更低 |
| prefixed | 1.9% 更快 | 30.3% 更低 |
| random | 9.6% 更慢 | 33.6% 更高 |
| sequential | 9.9% 更快 | 64.5% 更低 |

公共前缀 smoke 中，`prefix_length=32/64/80` 相比上一版时间分别降低约
`1.43% / 3.33% / 4.66%`，说明 OVG-direct 对长公共前缀场景有正向作用。

## 实验5优化后的性能 smoke

根据 `实验5.md` 的建议，已加入 Fused Check Window：短 Check 响应额外携带
`fused_window_bits=4` bit 的局部碰撞窗口，并把观察到的碰撞位缓存到子节点。
下一次处理该子节点时，如果缓存有效，则直接进入分裂规划，跳过一次 Inspect 响应。

同时在正式 OCG 配置中显式启用：

```text
enable_fused_check_window=True
fused_window_bits=4
```

并在消融实验中加入：

```text
HLCT-Base(no_fused_check)
```

已运行同口径 paired-seed 快速对比：

```text
实验名: formal_quick_comparison_exp5
标签数: 256
ID 长度: 64 bit
分布: random, prefixed, sequential, dispersed
重复次数: 每个点 3 次
输出目录: results/formal_quick_comparison_exp5/
```

HLCT-Base 相比 `HLCT-Base(no_fused_check)`：

| 场景 | 时间变化 | tag bits 变化 |
|---|---:|---:|
| random | ↓ 17.78% | ↓ 17.42% |
| prefixed | ↓ 23.51% | ↓ 17.39% |
| sequential | ↓ 22.36% | ↑ 5.49% |
| dispersed | ↓ 21.09% | ↓ 12.31% |

修复后 HLCT-Base 相比 DRCT：

| 场景 | 时间优势 | tag bits 优势 |
|---|---:|---:|
| random | 11.03% 更快 | 10.59% 更高 |
| prefixed | 25.08% 更快 | 42.58% 更低 |
| sequential | 30.08% 更快 | 62.50% 更低 |
| dispersed | 65.07% 更快 | 51.92% 更低 |

当前结论：Fused Check Window 明确提升了识别时间，并显著改善了此前 random
场景弱于 DRCT 的问题；sequential 场景 tag bits 略升，但时间仍明显下降。正式论文
数据仍建议使用 50-100 paired runs 重新生成置信区间。

## 实验6优化后的性能 smoke

根据 `实验6.md`，已继续增强 OVG：

- 新增 `prefix_stagnation_count`，当 collision child 的约束长度推进不足时触发 OVG。
- 新增 OVG 自适应统计和调度：`ovg_rehash_count`、`ovg_width_up_count`、
  `ovg_width_down_count`、`ovg_no_singleton_count`。
- OVG 后无 singleton 时优先 rehash / 调整 `r_h`，fallback 作为最后选项。
- 新增消融版本 `HLCT-Base(no_prefix_stagnation)`。
- 将正式默认参数调整为 `inspect_window_bits=8`、
  `prefix_stagnation_threshold=1`。该阈值比文档建议的 2 更激进，但 quick
  paired 调参显示它在 prefixed/dispersed 中有收益，且 random/sequential 不退化。

已运行同口径 paired-seed 快速对比：

```text
实验名: formal_quick_comparison_exp6
标签数: 256
ID 长度: 64 bit
分布: random, prefixed, sequential, dispersed
重复次数: 每个点 3 次
输出目录: results/formal_quick_comparison_exp6/
```

当前 HLCT-Base 相比实验5默认配置：

| 场景 | 时间变化 | tag bits 变化 | prefix-stagnation 触发 |
|---|---:|---:|---:|
| random | ↓ 0.07% | ↓ 7.51% | 0.00 |
| prefixed | ↓ 1.02% | ↓ 7.56% | 4.67 |
| sequential | 0.00% | 0.00% | 0.00 |
| dispersed | ↓ 0.74% | ↓ 6.60% | 7.00 |

当前 HLCT-Base 相比 DRCT：

| 场景 | 时间优势 | tag bits 优势 |
|---|---:|---:|
| random | 11.09% 更快 | 2.28% 更高 |
| prefixed | 25.84% 更快 | 46.92% 更低 |
| sequential | 30.08% 更快 | 62.50% 更低 |
| dispersed | 65.36% 更快 | 55.10% 更低 |

结论：实验6改进主要降低通信 bit，并在 prefixed/dispersed 这类 OVG 目标场景中
继续小幅降低识别时间；random 与 sequential 没有观察到时间退化。

## 实验7完善后的实验体系

根据 `实验7.md`，已将论文实验主线调整为 FCW-SGCT：

- 新增 `formal_fcw_window_sensitivity`，正式扫描 `fused_window_bits`。
- 新增 `HLCT-Base(fixed_8bit_check)` 消融。
- 新增 FCW 可观测指标：缓存创建、缓存命中、命中率、Inspect collision 次数。
- 保留 `enable_adaptive_fcw` 作为可选参数，但默认关闭。quick sweep 显示固定
  `fused_window_bits=4` 是更稳的全局折中。

已运行 FCW 窗口 quick sweep：

```text
实验名: formal_fcw_window_sensitivity_quick_exp7
标签数: 256
窗口: 0, 2, 4, 6, 8, 12, 16
场景: random, prefixed, dispersed, sequential, prefix80
重复次数: 每个点 3 次
输出目录: results/formal_fcw_window_sensitivity_quick_exp7/
```

关键观察：

| 场景 | 最快窗口 | 最低 tag bits 窗口 | 当前默认 w=4 评价 |
|---|---:|---:|---|
| random | 4 | 2 | 时间最优，tag bits 仅比最优高 0.83% |
| prefixed | 4 | 2 | 时间最优，tag bits 仅比最优高 0.17% |
| dispersed | 6 | 4 | tag bits 最优，时间比 w=6 慢 5.35% |
| sequential | 4 | 2/4 | 时间和 tag bits 均为最优组 |
| prefix80 | 8 | 2 | 时间比最优慢 0.44%，tag bits 接近最优 |

因此默认仍保留 `fused_window_bits=4`：它在 5 类场景中最稳，避免更大窗口在
random/sequential 中带来额外 tag bit 开销。

同口径 quick 消融结果：

```text
实验名: formal_quick_comparison_exp7
标签数: 256
场景: random, prefixed, dispersed, sequential, prefix80
重复次数: 每个点 5 次
输出目录: results/formal_quick_comparison_exp7/
```

FCW-SGCT 相比 `no_fused_check`：

| 场景 | 时间变化 | tag bits 变化 |
|---|---:|---:|
| random | ↓ 17.39% | ↓ 4.64% |
| prefixed | ↓ 42.94% | ↓ 12.99% |
| dispersed | ↓ 40.54% | ↓ 13.68% |
| sequential | ↓ 59.20% | ↓ 5.88% |
| prefix80 | ↓ 49.89% | ↓ 11.17% |

FCW-SGCT 相比 `no_check_gating` 的时间也大幅降低：random、prefixed、
dispersed、sequential、prefix80 分别约降低 `45.1% / 54.1% / 50.8% /
66.3% / 58.8%`。这说明当前最核心的性能贡献应写为
**Fused Check Window + Check-Gated EPC Verification**，OVG 更适合作为困难场景下的
skew-recovery 模块。

## 实验8完善后的审稿风险加固

根据 `实验8.md`，已继续补齐正式实验体系：

- 扩展 `formal_fcw_window_sensitivity`：新增 `prefix64`、`prefix72`、
  `clustered` 场景。
- 新增 `formal_ovg_stress_ablation`：专门比较 full、`no_ovg`、
  `no_prefix_stagnation` 在 `prefix64/prefix72/prefix80/dispersed/clustered`
  中的表现。
- 新增 `formal_check_gating_ablation`：正式比较 full、`no_fused_check`、
  `no_check_gating`、`fixed_8bit_check`、`no_check_escalation`、`no_ovg`、
  `no_prefix_stagnation`、`lock_only`、`cbit_only`。
- 新增 `clustered` 场景生成器，用多批次公共前缀模拟 batch EPC。
- 新增 `HLCT-Base(cbit_only)`，作为 DQTA-like 退化路径。

两个新增正式实验已完成 1-run smoke：

```text
results/formal_ovg_stress_ablation/
results/formal_check_gating_ablation/
```

OVG stress smoke 中，full 相比 `no_ovg` 的时间改善约为：

| 场景 | 时间改善 |
|---|---:|
| clustered | 1.50% |
| dispersed | 4.73% |
| prefix64 | 1.70% |
| prefix72 | 2.08% |
| prefix80 | 2.07% |

这个结果说明 OVG 已经有独立贡献，但贡献强度仍低于 FCW / Check-Gating。
因此论文叙述应把 OVG 定位为 skew-recovery 和长尾鲁棒性模块，而不是唯一核心贡献。

Check-Gating smoke 中，full 相比 `no_fused_check` 的时间改善在
`random/prefixed/prefix80/dispersed/sequential/clustered` 场景中均非常明显；
相比 `no_check_gating` 也有大幅优势。当前最稳妥的贡献排序仍是：

1. Fused Check Window；
2. Check-Gated EPC Verification；
3. Observation-driven Hybrid Split；
4. OVG with prefix-stagnation recovery。

## 验证命令

运行所有单元测试：

```bash
python -m unittest discover -s tests -v
```

编译检查所有 Python 文件：

```powershell
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
```

## 旧版实验脚本

旧版脚本仍可运行，但不保证所有算法在同一批 tag 上比较：

```bash
python Exp1.py
python Exp2.py
python Exp3.py
python Exp4.py
python exp5.py
python exp6.py
```

正式论文结果建议统一使用 `formal_experiment.py` 生成。



