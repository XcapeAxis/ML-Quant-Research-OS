# Excel 控制台 MVP

## 定位
- 用 Excel 桌面版替代当前本地网页，作为默认的内部研究监控入口。
- Python 继续是唯一真相源；Excel 只读取标准化 feed，不承载研究逻辑。
- 首页固定做成驾驶舱，不再把所有台账和低优先级信息挤在同一页。

## 当前交付
- 工作簿路径：`artifacts/projects/<project>/excel/ResearchConsole.xlsx`
- feed 路径：`artifacts/projects/<project>/excel/feed/`
- 说明文件：`artifacts/projects/<project>/excel/EXCEL_CONSOLE_NOTES.md`

当前版本覆盖：
- 当前阶段、主线、挑战者、blocker、下一步
- `F1 / F2 / 对照` 的核心指标
- 最近关键实验和策略账本
- 最近运行记录
- 最新图表预览
- 可复制的安全命令
  - `excel_export`
  - `research_audit`
  - `agent_cycle --dry-run`
  - `f1_verify`
  - `f2_verify`
  - 打开产物目录
  - 打开 tracked memory
  - 打开当前工作簿

当前版本不覆盖：
- `f2_train`
- 配置编辑
- 删除实验
- 从 Excel 直接写回 tracked memory
- VBA 宏执行
- `.cmd / .bat / .ps1 / .vbs` 启动器脚本

## 首页规则
- 首页是驾驶舱，不是全量台账。
- 首页只保留：
  - 当前主线
  - 当前 blocker
  - 下一步
  - 当前结论
  - `F1 / F2 / 对照` 核心指标
  - 最近验证能力
  - 安全命令清单
  - 一张大的主线对照图
  - 一张紧凑的主线对照表
- 详细账本放到：
  - `Overview`
  - `Strategies`
  - `Experiments`
  - `Runs`
  - `Artifacts`

## 语言与视觉
- 中文优先，策略 ID 保留英文。
- 首页优先保证 `100% ~ 125%` 缩放下可读，不追求一页塞更多内容。
- 如果首页再次拥挤，优先删减低优先级区块，而不是继续加块。

## 安全边界
- 当前工作簿固定为只读安全 `.xlsx`。
- 不再生成 `.cmd`、`.bat`、`.ps1`、`.vbs`、VBA 模块或任何可执行启动器脚本。
- 首页动作区只展示“可复制到终端”的安全命令，不直接执行命令。
- 重型训练和配置修改继续保留在终端完成。
- 导出时会自动清理旧的脚本和旧 `.xlsm` 残留，避免杀毒软件继续误报。

## 网页状态
- `apps/web`：冻结，不删除
- `dashboard/app.py`：冻结，不删除
- 只有当 Excel 已覆盖：
  - 项目概览
  - 实验账本
  - 最近验证结果
  - 安全命令
  并且用户明确确认后，才删除网页入口。
