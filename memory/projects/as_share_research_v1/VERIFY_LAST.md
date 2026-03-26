# 最近验证

- project_id: `as_share_research_v1`
- 当前主线: `risk_constrained_limit_up`
- 当前对照: `baseline_limit_up`
- 当前 blocker: drawdown > 30%，benchmark 角色已拆清。

## 通过命令
- `.venv\\Scripts\\python.exe -m pytest tests\\test_strategy_spec_consistency.py tests\\test_weekday_rebalance_contract.py tests\\test_manifest_and_memory_writeback.py tests\\test_leakage_guards.py tests\\test_response_contract.py tests\\test_canonical_project_identity.py tests\\test_research_readiness.py tests\\test_universe_profiles.py tests\\test_strategy_campaign.py -q`
- `.venv\\Scripts\\python.exe -m quant_mvp promote_candidate --project as_share_research_v1 --config configs\\projects\\as_share_research_v1.json`
- `.venv\\Scripts\\python.exe -m quant_mvp research_audit --project as_share_research_v1 --config configs\\projects\\as_share_research_v1.json`
- `.venv\\Scripts\\python.exe -m quant_mvp data_validate --project as_share_research_v1 --config configs\\projects\\as_share_research_v1.json`
- `.venv\\Scripts\\python.exe -m quant_mvp agent_cycle --project as_share_research_v1 --config configs\\projects\\as_share_research_v1.json --dry-run`

## 当前验证结论
- benchmark baseline: `pass`
- 研究基线宇宙 baseline 回撤: `56.50%`
- 研究基线宇宙候选主线 `risk_constrained_limit_up` 回撤: `47.29%`
