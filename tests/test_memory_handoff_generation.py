from __future__ import annotations

from quant_mvp.memory.writeback import bootstrap_memory_files, generate_handoff


REQUIRED_SECTIONS = [
    "## Current Total Task",
    "## Current Phase",
    "## Current Repo / Branch / HEAD",
    "## Confirmed Facts",
    "## Unconfirmed Questions",
    "## Recent Critical Failure",
    "## Current Blocker",
    "## Next Highest-Priority Action",
    "## Avoid Repeating Work",
    "## Required Verification First",
    "## Read These Files First If Context Is Thin",
    "## Tracked Memory Location",
    "## Runtime Artifacts Location",
    "## Current Real Capability Boundary",
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
