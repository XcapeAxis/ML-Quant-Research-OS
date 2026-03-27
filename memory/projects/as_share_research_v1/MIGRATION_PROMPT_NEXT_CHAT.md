# MIGRATION PROMPT NEXT CHAT
Project: `as_share_research_v1`
Universe: `cn_a_mainboard_all_v1`
Stage: `validation-ready`
Truth: coverage 已从 `51.11%` 修复到 `99.12%`；剩余 `28` 个缺口中，`24` 个是 `2025-07-01` 后上市新股，`4` 个是 provider failure。
Baseline: `baseline_validation_ready`
Guardrails: do not reopen legacy 715-symbol logic; do not promote baseline to active truth; do not restore `risk_constrained_limit_up` or `tighter_entry_limit_up`.
Next action: retry and classify `605296`, `605259`, `601665`, `601528` only.
