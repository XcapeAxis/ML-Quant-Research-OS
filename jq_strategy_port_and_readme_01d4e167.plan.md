---
name: Original Strategy Implementation and README
overview: Implement the project's original strategy (momentum + stop-loss + no-trade months) in SQLite/quant_mvp; extend backtest engine; add README and sync to GitHub. All code comments and docs in English; strategy described as original design only.
todos:
  - id: impl-1
    content: "Extend backtest_engine: stop-loss/take-profit/market-stoploss/blacklist/no-trade months/min commission; keep run_rebalance_backtest compatible"
    status: pending
  - id: impl-2
    content: Implement selection + Tuesday-only rebalance calendar (filters + momentum/start-point rank, output rank parquet)
    status: pending
  - id: impl-3
    content: "Add scripts/strategy_jq.py: config, selection, backtest call, artifact output; runnable standalone"
    status: pending
  - id: impl-4
    content: Add config 2026Q1_jq and pipeline hooks (optional 20/30 branch or strategy switch)
    status: pending
  - id: impl-5
    content: Write detailed README (English); describe strategy as original design; no reference to other platforms
    status: pending
  - id: impl-6
    content: Rename 123.py to scripts/strategy_jq.py; tidy project structure; ensure all comments/docs in repo are English
    status: pending
  - id: impl-7
    content: Git add, commit, push to origin (if remote configured)
    status: pending
isProject: false
---

# Original Strategy Implementation and README / GitHub Sync

**Constraint:** All user-facing documentation and in-repo code comments/docstrings must be in **English** only. The strategy must be described as **original design**; do not mention or imply that it comes from any other platform.

## 1. 策略对照与取舍

**123.py 核心逻辑摘要：**


| 模块    | 策略设计（原创）                                                                                             | 本地可行性                             | 建议                                                             |
| ----- | ---------------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------- |
| 标的池   | 全 A → 过滤次新/科创北交/ST/停牌/涨跌停 → 市值升序取前 1000                                                              | 10_symbols 已有主板+ST 过滤；无市值、无停牌/涨跌停 | 保留主板+ST；**小市值**用“现有 universe 截断”或后续接市值接口；涨跌停/停牌用“缺数据则跳过”或近似    |
| 选股    | 过滤涨停/跌停 → 历史涨停次数(3 年)取前 10% → 启动点排序 → 行业分散取 10 行业×2=20                                               | 无 high_limit；无行业(sw_l2)；无市值       | **简化**：用**动量(mom)或价格相对前低点的涨幅代替“启动点”；行业分散暂不实现**或占位              |
| 调仓    | 周二 10:15 卖、10:30 买，等权 6 只                                                                            | 当前为每 N 日调仓                        | **实现**：rebalance 仅取**周二**交易日（在 ranking/backtest 中按 weekday 过滤） |
| 空仓月   | 1 月 + 4 月持防御资产(5 只 ETF)                                                                              | 需防御资产行情                           | **实现**：若本地无 ETF 数据则改为**空仓持币**（equity 不变或现金收益为 0）               |
| 止损/止盈 | 个股止损线 0.91（价低于成本×0.91 即约 9% 亏损止损）、100% 止盈（价≥成本×2）；大盘趋势止损阈值 0.93（指数当日 close/open 均值≤0.93 时清仓）；拉黑 20 天 | 当前 backtest 无逐日持仓检查               | **实现**：扩展 `backtest_engine` 支持**日内止损/止盈**与**拉黑列表**（按日更新）       |
| 昨日涨停  | 昨日涨停且今日尾盘不涨停则卖                                                                                       | 需 high_limit                      | **近似**：用“昨日涨幅 ≥ 9.9%”近似涨停；若无则省略                                |
| 换手/放量 | 换手率异常或放量卖出                                                                                           | 需流通市值/换手                          | **暂不实现**（无流通市值）；或占位接口                                          |
| 成本    | 滑点 0.002，印花税 0.0005，佣金 0.0001，最低 5 元                                                                 | 当前为比例成本                           | 在 config 中改为与 123 一致；**最低 5 元**在 backtest 中可选实现                |


**止损/止盈逻辑澄清（避免表述错误）：**

- **个股止损**：`stoploss_limit=0.91` 表示当 **股价低于成本价的 91%** 时止损，即约 **9% 亏损** 触发。不可表述为“91% 止损”（易误解为跌 91% 才止损）。
- **止盈**：当 **股价 ≥ 成本价×2** 时止盈，即 **100% 盈利** 触发。表述“100% 止盈”正确。
- **大盘趋势止损**：`market_stoploss_ratio=0.93` 表示对基准指数成分股取 **当日 close/open** 的均值，若该比值 **≤ 0.93**（即当日平均跌幅约 7% 以上）则清仓。应表述为“大盘趋势止损阈值 0.93”或“指数当日 close/open 均值≤0.93 时清仓”，避免“93% 趋势止损”（易误解为跌 93%）。

**数据缺口与对策：**

- **涨跌停价**：AkShare 日线无 high_limit/low_limit；用 **close 与前一 close 的涨跌幅 ≥ 9.9%** 近似“涨停”，跌停同理。
- **市值**：当前 SQLite 无 valuation；可选后续接 AkShare 个股市值接口；**首版**用现有 universe + 动量排序代替“小市值前 1000”。
- **行业**：无 sw_l2；**首版**不做行业分散，仅保留“取前 2×stock_num 只”的接口，便于后续接入行业。
- **防御资产**：5 只 ETF 需单独行情；**首版**空仓月改为持币（不买 ETF），净值不变。

---

## 2. 实现方案

### 2.1 目录与文件角色

- **Strategy entry**：Rename **123.py** to **scripts/strategy_jq.py** as the executable entry for the project’s main (original) strategy; implement using `quant_mvp` and local data only.
  - Provides: stock selection (filters + momentum/start-point rank + Top 2×N), Tuesday rebalance dates, no-trade month mask, stop-loss/take-profit/blacklist params.
  - Callable from CLI or `scripts/steps/`; can also run standalone (read config, write artifacts). Remove or archive root 123.py as needed.
- **quant_mvp**：Extend to support the above; minimise breaking changes to existing API.
  - **[quant_mvp/backtest_engine.py](quant_mvp/backtest_engine.py)**：Add intraday stop-loss/take-profit, market trend stop-loss, blacklist, no-trade months, optional min commission.
  - **[quant_mvp/ranking.py](quant_mvp/ranking.py)** or new **quant_mvp/jq_ranking.py**：Tuesday-only rebalance calendar; selection pipeline (filters + momentum/start-point rank + top 2×stock_num), output compatible with existing `rank_topK.parquet`.
- **config**：新增或扩展现有项目 config（如 `2026Q1_jq`），包含：stock_num=6、rebalance_weekday=2、空仓月(1月+4月)、止损/止盈/大盘止损参数、拉黑天数、成本（滑点/印花税/佣金/最低佣金）。

### 2.2 123.py 改写结构（建议）

```text
scripts/strategy_jq.py（由 123.py 重命名）
├── 配置与常量（从 config 或模块内 DEFAULT 读取）
│   stock_num, rebalance_weekday, 空仓月, 止损线0.91/止盈2x/大盘0.93, 拉黑天数, 成本
├── 数据层（用 quant_mvp.db + Path）
│   load_bars_panel, 可选：涨跌停近似(基于涨跌幅)
├── 选股
│   filter_* (ST/次新/主板/科创北交 沿用 10_symbols 逻辑)
│   rank_by_momentum_and_start_point (动量 + 启动点近似)
│   get_rebalance_dates_tuesday(calendar, weekday=2)
├── 回测
│   调用 backtest_engine.run_rebalance_backtest_with_stoploss(
│     stoploss_limit=0.91, take_profit_ratio=2.0, market_stoploss_ratio=0.93,
│     loss_black_days, no_trade_months=[1,4], defense_etf_list=None
│   )
├── 主入口
│   if __name__ == "__main__": 解析 --project，load config，build rank，run backtest，save curves/metrics
```

- Implementation uses **batch daily backtest** only (loop over dates; rebalance on Tuesday; each day apply stop-loss/take-profit/market/blacklist). No real-time scheduler.

### 2.3 回测引擎扩展要点

- **run_rebalance_backtest** 增加可选参数（或新函数 **run_rebalance_backtest_with_stoploss**）：
  - `stoploss_limit=0.91`：当股价 &lt; 持仓成本×0.91 时止损（约 9% 亏损）；`take_profit_ratio=2.0`：当股价 ≥ 成本×2 时止盈（100% 盈利）；`market_stoploss_ratio=0.93`：当指数当日 close/open 均值 ≤ 0.93 时全部清仓（大盘单日大跌约 7% 以上）；
  - `loss_black_days=20`：在回测内维护 `set(code)` 及该 code 的“卖出日”，卖出日起 N 日内不可再买入；
  - `no_trade_months=[1,4]`：该月内不调仓、不买入股票，已有持仓按“持有到月末”或“月末清仓持币”两种模式（建议月末清仓持币）；
  - `min_commission=5`：每笔佣金 max(比例, 5)。
- 日内逻辑：每个交易日先根据当日 close 检查持仓是否触发止损/止盈/大盘止损，若触发则当日将该标的权重置 0（视为当日卖出），并更新拉黑列表；再执行 rebalance（若当日为周二且非空仓月）。

### 2.4 与现有 pipeline 的衔接

- **Option A (preferred)**：Keep `10_symbols`, `11_update_bars`; add **20_build_rank_jq.py** (or config-driven strategy in 20) for selection + Tuesday rebalance → `rank_top6.parquet`; **30_bt_rebalance.py** add stop-loss/no-trade-month switch or **30_bt_rebalance_jq.py** using extended backtest.
- **Option B**：strategy_jq.py as one-shot script: uses 10/11 data paths, builds rank, runs backtest with stop-loss, writes artifacts. Keep existing 20/30 for plain momentum.

Use **Option A**：**scripts/strategy_jq.py** as main strategy script; call `build_rank_*` and `run_*_backtest`; write to `artifacts/projects/<project>/`; compatible with existing report.

### 2.5 项目结构整理（保持整洁）

- 将 **123.py** 重命名为 **scripts/strategy_jq.py**，作为本策略唯一可执行入口；删除或归档根目录 123.py。
- 保持现有目录划分：`configs/`、`data/`、`artifacts/`、`quant_mvp/`、`scripts/`、`scripts/steps/`、`docs/`、`tests/`、`dashboard/`；策略脚本统一放在 `scripts/` 下（`strategy_jq.py` 与 `steps/` 并列）。
- 若有零散脚本可归入 `scripts/tools/` 或 `scripts/legacy/`，避免根目录堆砌。
- README 中的目录树与各目录职责与上述最终结构一致。

### 2.6 配置与文档

- 新增 **configs/projects/2026Q1_jq.json**（或合并进 2026Q1_mom）：加入 `strategy: "jq"`、`stock_num`、`rebalance_weekday`、`no_trade_months`、`stoploss_*`、`loss_black_days`、`commission`/`slippage`/`stamp_duty`/`min_commission`。
- **README**：见下文第 3 节。

---

## 3. README 设计（更详细，全英文）

README 使用 **English**，Markdown，表格与代码块，不配 emoji。**Do not mention any other platform; describe the strategy as original design only.**

- **Title and tagline**：e.g. Quant ML MVP — A-share momentum and stock-selection research platform (original strategy design).
- **Features**：Data (AkShare + SQLite), universe, selection (momentum / advanced strategy), backtest (equal weight, costs, stop-loss/take-profit/no-trade months), reporting and audit.
- **Strategy (original design)**：
  - Implemented in `scripts/strategy_jq.py`.
  - Logic: Tuesday rebalance; equal weight 6 names; **stoploss at 0.91** (sell when price &lt; cost×0.91, ~9% loss); **take-profit at 2× cost** (100% gain); **market stop-loss 0.93** (clear when index daily close/open mean ≤ 0.93); no-trade months (Jan + Apr) hold cash; 20-day blacklist after stop-loss.
  - Simplifications when data is missing: no market-cap/industry sort, no-trade months as cash, limit up/down approximated by daily return.
- **Quickstart**：Python version, install deps, fetch data (10→11), run strategy (`python scripts/strategy_jq.py --project 2026Q1_jq`) or momentum pipeline (20→30), view artifacts.
- **Project structure**：Directory tree and role of each dir; `scripts/strategy_jq.py` as main strategy entry.
- **Config**：Table of strategy-related config fields (stock_num, rebalance_weekday, no_trade_months, stoploss_limit, take_profit_ratio, market_stoploss_ratio, loss_black_days, cost params).
- **Data flow and reproducibility**：universe → bars → rank → backtest → report; list of files needed; example verify commands.
- **Syncing to GitHub**：Clone, commit, push; remote setup.
- **License / Disclaimer**：Research only; not investment advice.

**Codebase language:** All docstrings, comments, and user-facing strings in the repository must be in **English**.

---

## 4. 同步到 GitHub

- **允许自动执行**：实现完成后由 Agent 自动执行 `git add .`、`git status`、`git commit -m "..."`、`git push origin main`（或当前分支）。
- 若未配置 remote，先 `git remote -v` 检查；无 origin 则需用户提供仓库 URL 或跳过 push，并在总结中说明。
- README 中保留 **“同步到 GitHub”** 小节，说明日常提交与推送命令及 remote 配置。

---

## 5. 实现顺序（推荐）

1. **扩展 backtest_engine**：止损/止盈/大盘止损/拉黑/空仓月/最低佣金；保持现有 `run_rebalance_backtest` 签名兼容。
2. **选股与周二日历**：在 strategy_jq 或 quant_mvp 中实现选股（过滤 + 动量/启动点）+ 仅周二 rebalance 日期；输出 rank DataFrame/parquet。
3. **strategy_jq 主脚本**：整合配置、选股、回测调用、artifact 输出；可独立运行并可与 step 20/30 共用。
4. **配置与 pipeline 挂钩**：新增 2026Q1_jq config；可选 20/30 的策略分支或 30 的止损开关。
5. **README**：按第 3 节撰写并放入仓库根目录。
6. **GitHub**：按第 4 节自动执行 commit 与 push。
7. **项目结构整理（可选）**：为保持整洁，可做以下调整：将 123.py 重命名为 **scripts/strategy_jq.py** 并删除根目录 123.py；确保 `scripts/steps/` 与 `scripts/strategy_jq.py` 职责清晰；若有零散脚本可归入 `scripts/tools/` 或 `scripts/legacy/`；README 中的目录树与说明与最终结构一致。

---

## 6. 风险与后续

- **数据**：市值、行业、涨跌停价未接入时采用简化与假设；README 中写清 simplifications。
- **回测速度**：逐日止损/拉黑会多一层循环，可先用小 universe 或短区间验证。
- **后续**：接入市值/行业/涨跌停、防御资产 ETF、最低佣金精确实现。

---

## 7. 实施约束（必须遵守）

- **英文**：最终工程中所有说明、注释、docstring、README 及用户可见文案均为 **英文**。
- **原创表述**：对外（README、文档、注释）一律将策略描述为 **original design**，不提及、不暗示来自任何其他平台。

