# 最近验证快照
- branch: `main`
- 当前 canonical project: `as_share_research_v1`
- 当前 canonical universe: `cn_a_mainboard_all_v1`
- 当前阶段: `Canonical Universe Coverage Recovery / validation-ready`

## 通过的关键验证
- `.venv\Scripts\python.exe -m pytest tests/test_coverage_recovery.py tests/test_coverage_gap.py tests/test_research_readiness.py -q`
- `.venv\Scripts\python.exe -m quant_mvp coverage_recovery --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --rerun-baseline`
- `.venv\Scripts\python.exe -m quant_mvp data_validate --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --skip-clean`
- `.venv\Scripts\python.exe -m quant_mvp research_audit --project as_share_research_v1 --config configs/projects/as_share_research_v1.json`
- `.venv\Scripts\python.exe -m pytest tests/test_strategy_spec_consistency.py tests/test_weekday_rebalance_contract.py tests/test_manifest_and_memory_writeback.py tests/test_leakage_guards.py tests/test_coverage_recovery.py -q`

## 当前稳定结论
- coverage ratio: `99.12%`
- covered symbols: `3165 / 3193`
- campaign readiness stage: `validation-ready`
- data gate stage (`research_readiness.json`): `ready`
- baseline status: `baseline_validation_ready`
- legacy restore allowed: `false`

## 待继续验证
- 4 个 provider failure 的重试与分类
- baseline 后续是否能进入单独 promotion gate
