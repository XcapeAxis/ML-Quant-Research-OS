# 研究推进

- 当前轮次类型: 策略推进轮
- 系统推进: 本轮主要把当前研究结论、阻塞原因和后续验证顺序写清楚，没有新增宽泛系统扩张。
- 策略推进: 本轮围绕 f1_elasticnet_v1（F1 mainline） 继续收敛研究阻塞；当前最硬的限制仍是 F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.。
- 当前主线策略: f1_elasticnet_v1（F1 mainline）
- 当前 blocker: F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.
- 当前 blocked 策略: risk_constrained_limit_up（?????）, tighter_entry_limit_up（???????）
- 当前 rejected 策略: r1_predictive_error_overlay_v2（R1.2 ??）, r1_predictive_error_overlay_v1（R1.1 ??）, legacy_single_branch（?????）
- 下一步建议: Run one more bounded F2 variant before widening the search.
