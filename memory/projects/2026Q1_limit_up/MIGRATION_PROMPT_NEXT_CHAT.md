# Migration Prompt Next Chat

## Current Total Task
Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts.

## Current Phase
Phase 1 Research OS

## Current Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: 6d09a2ec898397c374f8dbeb4184cf22d657061b

## Confirmed Facts
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\2026Q1_limit_up\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\2026Q1_limit_up
- current_blocker: missing_research_inputs: No bars found for requested codes.

## Unconfirmed Questions
- No additional unconfirmed questions have been recorded yet.

## Recent Critical Failure
Dry-run blocked by missing research inputs: No bars found for requested codes.

## Current Blocker
missing_research_inputs: No bars found for requested codes.

## Next Highest-Priority Action
Restore a usable validated bar snapshot for the frozen default universe.

## Avoid Repeating Work
- Do not move durable memory back into ignored runtime directories.
- Do not trust default-project research claims until validated bars exist for the frozen universe.

## Required Verification First
- & .\\.venv\\Scripts\\python.exe -m pytest tests -q
- & .\\.venv\\Scripts\\python.exe -m quant_mvp memory_bootstrap --project 2026Q1_limit_up
- & .\\.venv\\Scripts\\python.exe -m quant_mvp memory_sync --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json
- & .\\.venv\\Scripts\\python.exe -m quant_mvp generate_handoff --project 2026Q1_limit_up

## Read These Files First If Context Is Thin
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\PROJECT_STATE.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\VERIFY_LAST.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\HANDOFF_NEXT_CHAT.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\RESEARCH_MEMORY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\POSTMORTEMS.md

## Tracked Memory Location
C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up

## Runtime Artifacts Location
- C:\Users\asus\Documents\Projects\BackTest\data\projects\2026Q1_limit_up\meta
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\2026Q1_limit_up

## Current Real Capability Boundary
Engineering guardrails work; real default-project research remains blocked on data coverage.
