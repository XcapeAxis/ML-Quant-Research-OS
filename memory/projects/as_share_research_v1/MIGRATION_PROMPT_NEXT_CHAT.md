# 下一轮迁移提示

## 当前总任务
把数据就绪 blocker 与策略质量 blocker 拆开判断，保持 promotion 结论诚实。

## 当前阶段
Phase 1 Research OS - promotion 评估

## 当前 Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: 9efa25a06e8f7003fd30c868a09a45232883135e

## 已确认事实
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- current_blocker: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.

## 未确认问题
- 当前尚未记录新的未确认问题。

## 最近关键失败
最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.

## 当前 blocker
最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.

## Subagent 状态
- gate_mode: AUTO
- active: none
- blocked: none
- recent_transition: iterative_relevance_review
- continue_using_subagents: 否

## 最近一次高阶迭代
- iteration_count: 1
- target_iterations: 3
- max_iterations: 5
- stop_reason: 同一 blocker 已升级且继续推进 ROI 很低，自动停止。
- direction_change: 否
- blocker_escalation: 是
- blocker_key: max_drawdown (repeat_count=4, historical_count=3)
- last_classification: blocker 已被澄清
- max_active_subagents: 0
- subagent_gate_mode: AUTO (blocked/retired/merged/archived=0/31/0/0)
- subagents_used: none
- subagent_reason: 任务广度尚未达到安全拆分的最低阈值。
- auto_closed_subagents: none
- alternative_subagents: none
- 本轮完成: 重复 blocker `max_drawdown` 并已停止自动重试。
- 本轮未完成: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 下一步建议: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。

## 下一步唯一建议
升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。

## 避免重复犯错
- 不要把 durable memory 再挪回被忽略的 runtime 目录。
- 在 frozen universe 具备已验证 bars 前，不要信任 default project 的研究结论。

## 必要验证优先
- python -m quant_mvp data_validate --project as_share_research_v1

## 如果上下文变薄，先读这些文件
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\PROJECT_STATE.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\VERIFY_LAST.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\HANDOFF_NEXT_CHAT.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\RESEARCH_MEMORY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\POSTMORTEMS.md

## Tracked Memory 位置
C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1

## Subagent 相关 tracked 文件
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_REGISTRY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_LEDGER.jsonl

## Runtime Artifacts 位置
- C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents

## 当前真实能力边界
研究输入已就绪，但候选仍未通过策略质量检查。
