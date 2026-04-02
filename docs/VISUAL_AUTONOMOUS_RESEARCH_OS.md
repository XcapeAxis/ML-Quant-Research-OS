# 可视化自治量化研发操作系统

## 1. 结论

这个项目值得继续，但必须换产品中心。

不再把目标定义成：
- 再做一个通用量化因子 / 机器学习可视化平台
- 再做一个低层节点拖拽工作流系统

而要把目标定义成：
- 一个面向量化研究的可视化自治研发操作系统
- 一个能编排、比较、审计、反思、淘汰和继承研究流程的上层控制面
- 一个能把本地 pipeline 和外部流程引擎都当作执行后端来调度的研究控制层

说得更直白一点：
- 外部流程引擎擅长把工作流做出来
- 这个仓库应该擅长决定做什么、为什么做、做完怎么评估、失败后怎么迭代

## 2. 新定位

### 2.1 一句话定位

一个面向量化研究的可视化自治研发操作系统。

### 2.2 面向的人

- 内部研究员
- 量化开发者
- 研究主管
- 未来的自治研究 agent

不是面向：
- 普通投资者的通用图形化回测玩具
- 低门槛通用节点平台用户

### 2.3 产品边界

本项目负责：
- 研究目标编排
- 研究对象建模
- 实验生命周期管理
- 候选策略 / 因子 / 特征 / 模型的比较与淘汰
- 验证、失败归因、审计
- 长期记忆、交接与反思
- worker / subagent 的任务分派与收口
- 工具与执行后端的接入治理

本项目不优先负责：
- 低层因子公式编辑器
- 通用数据处理节点广场
- 通用回测可视化平台
- 大量通用前端节点库

## 3. 命名体系

为避免系统围着某个外部品牌转，后续统一使用三层命名：

- 角色名：`Flow Engine` / `外部流程引擎`
- 集成名：`FlowBridgeAdapter`
- 真实来源：只保留在 `provider` 元数据里，例如 `provider = pandaai.quantflow`

固定规则：
- `BackendAdapter` 是抽象接口
- `FlowBridgeAdapter` 是“外部流程引擎桥接器”这一类实现
- `provider` 才是真实外部来源

以后不再把下面这些词当成系统中心命名：
- `PandaAdapter`
- `Panda backend`
- `Panda layer`
- `Panda-like platform`

真实品牌只应出现在：
- provider 字段
- 竞品分析
- 外部资料引用

## 4. 为什么要这样改

成熟外部平台已经覆盖了大量低层能力：
- 低层工作流节点
- 通用因子开发
- 通用机器学习节点
- 图形化回测和执行流程

这个仓库真正有差异化潜力的地方，不在低层节点，而在：
- tracked memory / handoff / migration prompt
- bounded verifier / challenger / control branch
- shared-shell 统一比较
- postmortem / failure analysis
- subagent / worker 编排
- 结构化研究对象

所以要把产品中心从“执行工具”改成“自治研发控制层”。

## 5. 四层架构

### 5.1 Research Graph

这是研究真相层。

核心对象：
- `ResearchMission`
- `ResearchBranch`
- `DatasetSnapshot`
- `UniverseSnapshot`
- `FeatureView`
- `LabelSpec`
- `FactorCandidate`
- `ModelCandidate`
- `StrategyCandidate`
- `Experiment`
- `EvaluationRecord`
- `DecisionRecord`
- `FailureRecord`
- `BackendAdapter`
- `BackendRun`

职责：
- 把研究过程中的关键对象结构化
- 让系统能比较“两个实验到底差在哪”
- 让可视化层不再自己拼真相

### 5.2 Research Orchestrator

这是自治编排层。

职责：
- 拿到研究目标
- 自动拆分为多个 branch
- 为 branch 分预算和 stop rules
- 生成实验任务
- 调度 worker
- 汇总 verifier 结果
- 决定 keep / reject / escalate / archive

### 5.3 Execution Adapter Layer

这是执行后端接入层。

系统不要求所有执行能力都在本仓库里重做，而是允许把外部流程引擎接进来。

第一阶段固定支持两类后端：
- `LocalPipelineAdapter`
- `FlowBridgeAdapter`

其中：
- `LocalPipelineAdapter` 调用仓库内已有训练、验证、shared-shell 与 writeback 逻辑
- `FlowBridgeAdapter` 调用外部流程引擎

`FlowBridgeAdapter` 的真实来源示例：
- `provider = pandaai.quantflow`
- `provider_display_name = Panda QuantFlow`

### 5.4 Visual Research Console

这是可视化层。

可视化重点不是低层拖拽节点，而是：
- Mission Cockpit
- Branch Board
- Experiment Lineage
- Failure Board
- Worker Board
- Adapter Board

## 6. 可视化对象应该是什么

如果系统要可视化，第一等节点应该是“研究语义节点”，而不是低层 ETL 节点。

建议的一等对象：

### 6.1 Mission
- 研究目标
- 市场范围
- 时间范围
- 风险约束
- 预算
- 成功标准

### 6.2 Universe
- 股票池快照
- 过滤条件
- 数据覆盖状态

### 6.3 Feature / Label
- 特征视图
- 标签定义
- 样本边界
- 可复现指纹

### 6.4 Model
- 模型候选
- 参数
- 更新频率
- 是否在线自适应

### 6.5 Verify
- control vs challenger 比较
- shared-shell 指标
- drawdown / sharpe / calmar / turnover

### 6.6 Reflection
- 为什么失败
- 是收益问题还是回撤问题
- 是数据问题还是模型问题
- 是否值得继续

### 6.7 Decision
- keep as mainline
- keep as challenger
- reject
- rerun bounded variant
- widen search
- spawn scouting

### 6.8 Memory
- 写回结论
- 写回 blocker
- 写回下一步动作
- 生成 handoff / migration / verify 快照

## 7. 页面结构

### 7.1 Mission Cockpit
- 当前 mission
- 当前主线
- 当前 challenger
- 当前 blocker
- 最近 verifier
- 下一步动作
- 当前 active workers

### 7.2 Branch Board
- 所有 branch
- 当前状态
- 最近实验
- 最近结论
- 是否继续

### 7.3 Experiment Lineage
- 从谁分叉出来
- 改了什么
- 为什么做
- 结果是否更好
- 是否被保留

### 7.4 Failure Board
- 最近失败实验
- 失败原因分类
- 重复 blocker
- 当前常见失败模式
- 下一轮建议

### 7.5 Worker Board
- 当前有哪些 scouts / implementers / verifiers
- 在做什么
- 绑定哪个 branch
- 是否应该退役

### 7.6 Adapter Board
- 当前有哪些执行后端
- LocalPipelineAdapter
- FlowBridgeAdapter
- provider 信息
- 最近成功 / 失败记录

## 8. FlowBridge 集成策略

### 8.1 不替代外部平台

不要把目标定成“替代成熟外部流程引擎的全部能力”。

### 8.2 把外部平台当执行后端

`FlowBridgeAdapter` 只做统一桥接。

建议输入：
- universe snapshot
- feature view
- label spec
- workflow template id
- parameter overrides
- execution budget

建议输出：
- backend run id
- status
- metrics
- artifact paths
- logs
- lineage metadata
- failure reason

系统负责：
- 决定何时调用外部流程引擎
- 选择模板和参数
- 把结果回收到统一 verifier
- 把失败写回长期记忆

## 9. 路线图

### 9.1 Phase A：定位纠偏
- 停止继续向通用量化平台扩张
- 重写产品定位和架构
- 冻结错误方向

### 9.2 Phase B：Research Graph
- 固定高层研究对象
- 先可视化研究对象，不先可视化低层执行图

### 9.3 Phase C：Execution Adapter
- 做 `LocalPipelineAdapter`
- 做 `FlowBridgeAdapter`
- 做 artifact ingestion contract

### 9.4 Phase D：Autonomous Loop
- 自动生成下一轮实验
- 自动比较 challenger
- 自动写回记忆

### 9.5 Phase E：Visual Autonomous R&D
- mission cockpit
- branch lineage
- worker board
- adapter board
- replay / audit view

## 10. 明确不做什么

- 不重做一个庞大的通用可视化因子平台
- 不重做一个庞大的通用图形化回测工具
- 不先做一堆低层拖拽节点
- 不把 UI 壳层当成产品中心
- 不把“可视化”误解成“低层拖拽编辑器”

## 11. 当前最应该做的下一步

只做三件事：
1. 固定 `FlowBridgeAdapter` 契约
2. 固定 `mission / branch / experiment / decision / failure / worker / adapter` 对象模型
3. 先做高层研究驾驶舱的信息架构，不做低层执行图编辑器

## 12. 最后一句

如果继续做“另一个通用量化工作流平台”，胜率很低。

如果改做“外部流程引擎之上的自治研发控制层”，这个项目反而更有理由继续。
