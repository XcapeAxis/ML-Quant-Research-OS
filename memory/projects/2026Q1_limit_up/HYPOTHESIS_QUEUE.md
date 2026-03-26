# 假设队列

1. [阻塞] 先恢复 2026Q1_limit_up 可用日频 bars，再从 baseline_limit_up 开始第一轮 bounded validation。
2. [待处理] 如果 bars 恢复后主线仍因回撤卡住，优先比较 risk_constrained_limit_up 与 baseline_limit_up。
3. [待处理] 只在主线 blocker 缩小后再启动 tighter_entry_limit_up 的对照验证。
