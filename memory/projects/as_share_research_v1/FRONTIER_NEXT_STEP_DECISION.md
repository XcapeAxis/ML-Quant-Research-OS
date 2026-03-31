# 前沿下一步决策

## 当前瓶颈
- 当前主线仍是 `f1_elasticnet_v1`。
- 已确认事实：`F1` 在同一 core universe、同一 shared shell 下明显强于 `baseline_limit_up`。
- 已确认失败路径：`R1.2` 虽然把 shared-shell `Top6 max_drawdown` 从 `-37.10%` 压到 `-25.47%`，但把年化收益从 `52.73%` 拉低到 `39.08%`，收益损失超过允许的 `3` 个百分点，所以不能继续作为下一控制层主推方向。
- 当前唯一要锁定的问题已经不是“是否继续打磨 R1 家族”，而是“下一条正式 challenger 选谁”。

## 结果
- winner: `F2.1`
- runner-up: `Hybrid F1.5`
- rejected_this_round: `R1.2`
- deferred_backlog: `X1`, `financial world model`, `MARL`

## 候选排序
| 候选 | drawdown 改善潜力 | 额外 alpha 潜力 | 实现复杂度可控性 | 算力/依赖成本可控性 | 接线难度 | 可审计性/过拟合风险 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `F2.1` | 3 | 4 | 3 | 3 | 4 | 3 | winner |
| `Hybrid F1.5` | 2 | 3 | 1 | 1 | 2 | 2 | runner-up |
| `R1.2` | 4 | 2 | 4 | 5 | 4 | 4 | rejected_this_round |

## 各路线结论
### 1. `F2.1` | winner
- 结论：`F2.1 structured latent deep factor` 现在是下一条正式实现路线。
- 核心证据：
  - `R1.2` 已经证明“继续在 exposure-only overlay 家族里打磨”不能稳定守住收益底线。
  - 当前对象层已经能承接 `FeatureView / ModelCandidate / Experiment / EvaluationRecord`，不需要推倒重来。
  - 相比 foundation sidecar，`F2.1` 更容易在当前 repo 的 walk-forward、shared shell 和实验账本里保持可审计。
- 主要风险：
  - 现有特征底座仍偏薄，若原型过早依赖重模型，可能只是在放大过拟合空间。
  - 若实现滑向 CUDA-only 或重 PyTorch 依赖，平台复杂度会明显上升。
- 明确 no-go：
  - 若原型需要新的重依赖、无法在当前 monthly retrain + shared shell 契约下做清晰 walk-forward，就立即降级，不强推。
- 最小原型建议：
  - 先做 `structured latent deep factor`，不把 `Mamba/S4` 当近端默认实现。
  - 继续复用 `F1` 的 `core universe`、`next_5d_excess_return` 标签和 monthly retrain 节奏。
  - 验证目标仍固定为与 `F1` 在同一 shared shell 下做 bounded 对比。
- 未解决未知项：
  - 仅凭当前 OHLCV + 流动性特征，latent factor 是否足够有信息量，仍需首个 bounded prototype 才能回答。

### 2. `Hybrid F1.5` | runner-up
- 结论：保留为 runner-up，但仍不进入近端实现。
- 核心证据：
  - frozen sidecar 方向理论上成立，但当前 repo 对外部模型权重、离线缓存、复现治理还不够稳。
  - 它比 `F2.1` 更依赖额外基础设施，不适合作为当前最短路径。
  - 它不比 `F2.1` 更直接解决当前 blocker。
- 主要风险：
  - 依赖和复现成本高。
  - 容易让平台从可审计研究系统滑向难复现实验堆。
- 明确 no-go：
  - 若需要在线下载大模型、不可固定权重、或无法离线复现，就继续 defer。
- 最小原型建议：
  - 未来最多做 frozen encoder sidecar，只输出少量附加特征，不接管主训练流程。
- 未解决未知项：
  - 在当前 A 股日频数据厚度下，foundation sidecar 是否真的能提供比本地特征更稳定的增量信息，仍没有直接证据。

### 3. `R1.2` | rejected_this_round
- 结论：`R1.2` 到此为止，不再作为下一实现位继续打磨。
- 核心证据：
  - `annualized_return_delta = -13.65%`，明显低于允许的 `-3.00%` floor。
  - 虽然 `max_drawdown` 改善了 `11.63` 个百分点，但当前收益代价过高。
  - 这说明在当前 `F1` 契约下，继续做更软的 exposure-only overlay 也没有足够高的近端性价比。
- 主要风险：
  - 若继续在同一家族里调阈值，很容易变成低价值参数热修。
- 明确 no-go：
  - 不再继续做 `R1.2 v1.x` 这类“小幅调阈值”迭代。
- 最小原型建议：
  - 无。该分支保留在失败记忆中，仅作为负面参考。
- 未解决未知项：
  - regime 控制方向并未被永久否定，只是当前 exposure-only 版本不值得继续近端投入。

## 未选原因
- 未继续选 `R1.2`：因为它已经被真实验证拒绝，而不是“还没来得及试”。
- 未把 `Hybrid F1.5` 升为 winner：因为依赖、复现和治理成本仍然过高。

## 下一步最小原型范围
- 只做一个 bounded `F2.1` prototype。
- 不新增重依赖，不默认引入 CUDA-only 栈。
- 不改 `F1` control branch 的现有比较口径。
- 继续使用当前 core universe、标签契约、monthly retrain 和 shared shell。
- 首版目标是回答“`F2.1` 是否能在不放大复杂度的前提下改善 `F1` 的回撤/收益权衡”，不是证明盈利。

## 关键引用
- `R1.2` 失败证据：
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
- `F2.1` 接线基础：
  - `C:\Users\asus\Documents\Projects\BackTest\quant_mvp\f1_pipeline.py`
  - `C:\Users\asus\Documents\Projects\BackTest\quant_mvp\experiment_graph.py`
  - `C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\FRONTIER_ALGO_SURVEY_20260330.md`
