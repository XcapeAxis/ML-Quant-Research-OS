# Migration Prompt For Next Chat

You are not taking over a new repo. You are continuing the current `BackTest` repo after the canonical project has already switched to `crypto_okx_research_v1`.

## Accept These Facts First
- The current mainline is `Backtest First + Crypto + OKX`.
- `BackTest` is the only research-kernel repo.
- `OpenClaw` is the only control repo.
- `article_lab` is second priority only.
- `BalatroAI` is maintenance-only.

## The Real Blocker
Do not reframe this as a missing-data problem.

The actual blocker is:
- `tests/test_platform_api.py` still has broken strings
- `pytest` fails during collection because of syntax errors

## What To Do First
1. Read `HANDOFF_NEXT_CHAT.md`
2. Repair `tests/test_platform_api.py`
3. Run the required tests
4. Then check whether any Phase 0 gap still remains
5. After that, review how many verified bug fixes were completed in this cycle

## What Not To Do
- Do not start with feature work
- Do not start with UI work
- Do not widen the market scope
- Do not claim the blocker is still missing OKX bars without checking the current doctor output

## Remember
The current task is to make the mainline verifiable, not to make the scope bigger.
