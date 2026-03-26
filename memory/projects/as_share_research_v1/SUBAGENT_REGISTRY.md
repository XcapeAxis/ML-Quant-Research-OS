# Subagent 注册表

## 治理概况
- gate_mode: AUTO
- recommended_gate: OFF
- 是否继续使用 subagents: 否
- 继续原因: 任务广度尚未达到安全拆分的最低阈值。
- 最近事件: iterative_relevance_review

## 当前集合
- active: none
- blocked: none
- retired: sa-001, sa-002, sa-003, sa-004, sa-005, sa-006, sa-007, sa-20260325150849781070-932c, sa-20260325150851246437-8049, sa-20260325150857703676-306c, sa-20260325150859131657-2e6d, sa-20260325150905477175-ee0b, sa-20260325150906960445-8e82, sa-20260325150925548166-7fcd, sa-20260325150926924590-bb25, sa-20260325151502176602-ee4c, sa-20260325151503532918-ed2b, sa-20260325151509622682-dce5, sa-20260325151511046386-a98f, sa-20260325151516876234-eee5, sa-20260325151518290134-5820, sa-20260325151536002718-d679, sa-20260325151537316765-574a, sa-20260325152148073676-e478, sa-20260325152149433166-7cc9, sa-20260325152154074736-0f4a, sa-20260325152155435374-98ca, sa-20260325152200232912-ef56, sa-20260325152201594111-9c87, sa-20260325152220234694-cb14, sa-20260325152221633066-3c39
- merged: none
- archived: none
- canceled: none
- refactored: none
- 临时实例: sa-001, sa-002, sa-003, sa-004, sa-005, sa-006, sa-007, sa-20260325150849781070-932c, sa-20260325150851246437-8049, sa-20260325150857703676-306c, sa-20260325150859131657-2e6d, sa-20260325150905477175-ee0b, sa-20260325150906960445-8e82, sa-20260325150925548166-7fcd, sa-20260325150926924590-bb25, sa-20260325151502176602-ee4c, sa-20260325151503532918-ed2b, sa-20260325151509622682-dce5, sa-20260325151511046386-a98f, sa-20260325151516876234-eee5, sa-20260325151518290134-5820, sa-20260325151536002718-d679, sa-20260325151537316765-574a, sa-20260325152148073676-e478, sa-20260325152149433166-7cc9, sa-20260325152154074736-0f4a, sa-20260325152155435374-98ca, sa-20260325152200232912-ef56, sa-20260325152201594111-9c87, sa-20260325152220234694-cb14, sa-20260325152221633066-3c39
- 长生命周期模板: none

## 最新计划
- recommended_count: 0
- recommended_roles: none
- 不拆分原因: 任务广度尚未达到安全拆分的最低阈值。
- 计划理由: 当前工作仍足够单线，保持一个整合代理最稳妥。

## 角色模板
- data_steward: Own provider, ingestion, cleaning, and data coverage diagnostics without changing strategy logic.
- strategy_auditor: Check strategy entrypoints, defaults, and documentation for drift.
- validation_guard: Own leakage, robustness, baseline, and promotion-gate verification work.
- memory_curator: Keep tracked memory, handoff, and migration prompts concise and accurate.
- tooling_scout: Investigate missing tools, policy files, and reproducibility boundaries before anything is added.
- integration_merger: Merge compatible workstreams, reduce overlap, and close out temporary subagents.

## 实例记录
### sa-001 | scout | 已退休
- 摘要: scout task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-001
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-002 | scout | 已退休
- 摘要: scout task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-002
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-003 | implementer | 已退休
- 摘要: implementer task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__legacy_single_branch__20260325T150231Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-003
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-004 | scout | 已退休
- 摘要: scout task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-004
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-005 | implementer | 已退休
- 摘要: implementer task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__risk_constrained_limit_up__20260325T150231Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-005
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-006 | scout | 已退休
- 摘要: scout task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-006
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-007 | implementer | 已退休
- 摘要: implementer task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__tighter_entry_limit_up__20260325T150231Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-007
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150849781070-932c | scout | 已退休
- 摘要: scout task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150849781070-932c
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150851246437-8049 | implementer | 已退休
- 摘要: implementer task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__baseline_limit_up__20260325T150840Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150851246437-8049
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150857703676-306c | scout | 已退休
- 摘要: scout task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150857703676-306c
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150859131657-2e6d | implementer | 已退休
- 摘要: implementer task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__risk_constrained_limit_up__20260325T150840Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150859131657-2e6d
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150905477175-ee0b | scout | 已退休
- 摘要: scout task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150905477175-ee0b
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150906960445-8e82 | implementer | 已退休
- 摘要: implementer task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__tighter_entry_limit_up__20260325T150840Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150906960445-8e82
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150925548166-7fcd | scout | 已退休
- 摘要: scout task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150925548166-7fcd
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325150926924590-bb25 | implementer | 已退休
- 摘要: implementer task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__legacy_single_branch__20260325T150915Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325150926924590-bb25
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151502176602-ee4c | scout | 已退休
- 摘要: scout task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151502176602-ee4c
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151503532918-ed2b | implementer | 已退休
- 摘要: implementer task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__baseline_limit_up__20260325T151453Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151503532918-ed2b
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151509622682-dce5 | scout | 已退休
- 摘要: scout task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151509622682-dce5
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151511046386-a98f | implementer | 已退休
- 摘要: implementer task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__risk_constrained_limit_up__20260325T151453Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151511046386-a98f
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151516876234-eee5 | scout | 已退休
- 摘要: scout task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151516876234-eee5
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151518290134-5820 | implementer | 已退休
- 摘要: implementer task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__tighter_entry_limit_up__20260325T151453Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151518290134-5820
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151536002718-d679 | scout | 已退休
- 摘要: scout task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151536002718-d679
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325151537316765-574a | implementer | 已退休
- 摘要: implementer task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__legacy_single_branch__20260325T151529Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325151537316765-574a
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152148073676-e478 | scout | 已退休
- 摘要: scout task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152148073676-e478
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152149433166-7cc9 | implementer | 已退休
- 摘要: implementer task for baseline_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__baseline_limit_up__20260325T152141Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152149433166-7cc9
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152154074736-0f4a | scout | 已退休
- 摘要: scout task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152154074736-0f4a
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152155435374-98ca | implementer | 已退休
- 摘要: implementer task for risk_constrained_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__risk_constrained_limit_up__20260325T152141Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152155435374-98ca
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152200232912-ef56 | scout | 已退休
- 摘要: scout task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152200232912-ef56
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152201594111-9c87 | implementer | 已退休
- 摘要: implementer task for tighter_entry_limit_up
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__tighter_entry_limit_up__20260325T152141Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152201594111-9c87
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152220234694-cb14 | scout | 已退休
- 摘要: scout task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: branch_pool_snapshot, candidate_notes
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152220234694-cb14
- 生命周期: parents=none; children=none; merged_into=n/a
### sa-20260325152221633066-3c39 | implementer | 已退休
- 摘要: implementer task for legacy_single_branch
- 临时实例: 是
- allowed_paths: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\pools\branch, C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta\experiments, C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents
- expected_artifacts: as_share_research_v1__legacy_single_branch__20260325T152213Z
- artifact_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents\sa-20260325152221633066-3c39
- 生命周期: parents=none; children=none; merged_into=n/a
