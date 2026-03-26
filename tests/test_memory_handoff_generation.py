from __future__ import annotations

from quant_mvp.memory.writeback import bootstrap_memory_files, generate_handoff


REQUIRED_SECTIONS = [
    "## 当前总任务",
    "## 当前阶段",
    "## 项目身份",
    "## 当前研究对象",
    "## 当前 Repo / Branch / HEAD",
    "## 已确认事实",
    "## 未确认问题",
    "## 最近关键失败",
    "## 当前 blocker",
    "## Subagent 状态",
    "## 最近策略动作",
    "## 下一步唯一建议",
    "## 避免重复犯错",
    "## 必要验证优先",
    "## 如果上下文变薄，先读这些文件",
    "## Tracked Memory 位置",
    "## Strategy 相关 tracked 文件",
    "## Runtime Artifacts 位置",
]


def test_generate_handoff_and_migration_prompt(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    generate_handoff(project)

    assert paths.handoff_path.exists()
    assert paths.migration_prompt_path.exists()

    migration_prompt = paths.migration_prompt_path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in migration_prompt

    handoff = paths.handoff_path.read_text(encoding="utf-8")
    assert "# 下一轮交接" in handoff
    assert "## 项目身份" in handoff
    assert "## 当前研究对象" in handoff
    assert "## 当前 active 研究型 subagents" in handoff
    assert "## 最近策略动作" in handoff
    assert "## 最近一次高阶迭代" in handoff
