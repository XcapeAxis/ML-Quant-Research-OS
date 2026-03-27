# 最近验证快照

- branch: `main`
- 当前 canonical project: `as_share_research_v1`
- 当前 canonical universe: `cn_a_mainboard_all_v1`
- 当前阶段: `universe reset / baseline rebuild`

## 通过的关键验证
- `python scripts/steps/10_symbols.py`
  - 结果: 重建 `security_master.csv` 与 `universe_codes.txt`
  - 关键指标: `universe_id=cn_a_mainboard_all_v1`, `size=3193`
- `python -m quant_mvp research_audit --project as_share_research_v1 --config configs/projects/as_share_research_v1.json`
  - 结果: 研究审计通过，当前 blocker 被正确识别为 readiness 不足
- `python -m quant_mvp agent_cycle --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --dry-run`
  - 结果: control plane 干跑通过，promotion gate 正确被 readiness 拦住
- `python scripts/run_limit_up_screening.py --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --save none --no-show`
  - 结果: 新 universe 上 baseline 最小重建流程可跑通，但只属于 pilot 级别验证
- `pytest tests/test_canonical_project_identity.py tests/test_akshare_column_mapping.py tests/test_universe_profiles.py tests/test_coverage_gap.py tests/test_agent_cycle_dry_run.py`
  - 结果: 通过
- `pytest tests -q`
  - 结果: `110 passed`

## 稳定数据结论
- 最新稳定 coverage ratio: `51.11%`
- 最新稳定 covered symbols: `1632 / 3193`
- 最新 stable readiness stage: `pilot`

## 当前边界
- 当前只能确认: 新 universe 已建立，旧池子已退出 active path，baseline 重建已启动。
- 当前不能确认: 任一策略已经在新 canonical universe 上形成可晋级结论。

## 回归观察名单结论
- universe materialization: 通过
- ST 标签保留且不筛除: 通过
- old pool active 引用清理: 通过
- baseline rebuild completeness: 未通过，仍受 coverage 限制
