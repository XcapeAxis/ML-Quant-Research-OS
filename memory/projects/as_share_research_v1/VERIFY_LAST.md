# 最近验证快照

## 规范项目
- project_id: `as_share_research_v1`
- legacy_alias: `2026Q1_limit_up`
- 当前主线策略: `baseline_limit_up`
- 当前研究阶段: 晋级受阻
- configured_gate: `AUTO`
- effective_gate_this_run: `OFF`

## 通过命令
- `.venv\Scripts\python.exe -m pytest tests\test_strategy_spec_consistency.py tests\test_weekday_rebalance_contract.py tests\test_manifest_and_memory_writeback.py tests\test_leakage_guards.py tests\test_subagent_policy.py tests\test_subagent_lifecycle.py tests\test_response_contract.py tests\test_iterative_loop.py tests\test_mission_tick.py tests\test_strategy_visibility.py tests\test_memory_handoff_generation.py tests\test_verify_snapshot.py tests\test_canonical_project_identity.py -q`
- `.venv\Scripts\python.exe -m quant_mvp data_validate --project as_share_research_v1`
- `.venv\Scripts\python.exe -m quant_mvp research_audit --project as_share_research_v1`
- `.venv\Scripts\python.exe -m quant_mvp agent_cycle --project as_share_research_v1 --dry-run`
- `.venv\Scripts\python.exe -m quant_mvp promote_candidate --project as_share_research_v1`

## 当前结论
- 默认项目数据状态: `715/715` validated symbols，研究输入 ready
- 工程边界: canonical identity、strategy action log、handoff、migration prompt、subagent registry、Chinese reporting 均已刷新
- 研究边界: 当前不是缺 bars，而是 promotion-stage failure
- 直接 promotion gate 结果: `max drawdown 50.44% > 30.00%`，并伴随 `benchmark_missing:000001`
- 旧 dry-run evaluator 结果: 只保留为历史对照，不再代表当前 canonical truth
