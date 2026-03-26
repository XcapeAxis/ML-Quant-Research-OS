# 研究记忆

## 长期事实
- The long-term north star is still an autonomous quant research agent that can research, iterate, reflect, search for missing tools, operate tools, mine opportunities and factors, and use subagents adaptively.
- Stage 0A completed by shrinking the default project from 3063 symbols to a data-ready 715-symbol range；all stronger research claims must stay inside that restored range.
- The v1 core research pool is built from the restored 715-symbol range and currently keeps 492 mainboard names after ST, history, recent-volume, and liquidity filters.
- Architecture Slice 2 is now live: mission_tick writes mission, branch, and evidence ledgers, formal experiment JSON records, and real scout or implementer worker-task artifacts.
- agent_cycle is only a compatibility shell on top of mission_tick and must not overwrite the primary multi-branch mission state.
- Subagents are now a dynamic resource: the system should switch them on, downgrade them, pause them, or retire them according to real-time task needs instead of keeping them always active.
- Worker subagent ids are collision-resistant so concurrent or closely spaced runs no longer reuse the same tracked id by accident.
- Old strategy scripts still prefer the legacy project universe file when it exists, and only fall back to the new core pool when that file is missing；this is an intentional compatibility bridge, not the final architecture.
- Promotion gate baseline wiring was repaired earlier, and this run completed the remaining benchmark fix by loading the configured benchmark series independently from ranked codes.
- On the current `as_share_research_v1` run, both `promote_candidate` and `agent_cycle --dry-run` now report `baselines_status=pass`, `benchmark_available=true`, and `equal_weight_available=true`.
- The stored readiness artifacts still classify the current 492-name core validated snapshot as ready for promotion-grade checks, so the live blocker is max drawdown 56.50% rather than generic missing bars or benchmark completeness.
- `equal_weight_total_return` remains `1.0497515982053982` after the benchmark repair, so the fix did not widen the equal-weight baseline definition.
- Some readiness payloads still carry the legacy project label `2026Q1_limit_up` even though `as_share_research_v1` is now the live default-project name.

## 负面记忆
- Do not describe queued verifier tasks as if full verification already happened.
- Do not treat the 492-name core research pool as a drop-in replacement for every old strategy path before replacement tests are done.
- Do not treat the current compatibility fallback in strategy scripts as a finished dual-pool migration.
- Do not keep subagents permanently active out of habit；if a transient worker has finished, pause or retire it.
- Do not run parallel top-level commands that write the same tracked project state as if they were concurrency-safe research execution.
- Do not claim tool autonomy, multi-direction search, or profitable superagent behavior from Slice 2；verifier execution is still partial and the strategy still fails promotion.
- Do not reopen generic benchmark-missing diagnosis on `as_share_research_v1` unless `baselines_status` falls below `pass`；that wiring bug is fixed.
- Do not rely on `python -m quant_mvp research_readiness` as a callable CLI step in the current build；use the stored readiness artifacts or supported commands instead.

## 下一步记忆
- 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
- 恢复 frozen default universe 可用的 validated bar 快照。
- 先对 `max_drawdown` 做更细的根因诊断，再决定是否进入下一轮 automation iteration。
- 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- Use STRATEGY_FAILURE_REPORT and the branch ledger to choose the first bounded drawdown-focused experiment now that baseline completeness passes.
