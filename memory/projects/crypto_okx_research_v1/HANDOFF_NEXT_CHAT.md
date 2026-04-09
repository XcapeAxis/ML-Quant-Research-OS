# Next Chat Handoff

## Current Goal
Prove that `crypto_okx_research_v1` has a real research loop before any demo or live work.

## Current Phase
- Phase: `phase-0-backtest-first`
- Market: `crypto`
- Exchange: `okx`

## Current Truth
- Canonical project: `crypto_okx_research_v1`
- Repo root: `C:\Users\asus\Documents\Projects\BackTest`
- The current blocker is not missing OKX data.
- The current blocker is `tests/test_platform_api.py`, which still has broken strings from earlier bad encoding.
- `pytest` stops during collection with an unterminated string around line `528`.

## Verified Facts
- `python -m quant_mvp.cli doctor --project crypto_okx_research_v1` currently passes.
- The doctor result shows:
  - OKX instruments: `200`
  - OKX candles: `200`
  - OKX funding history: `200`
  - BTC and ETH swap data exists in the target window
- `crypto_okx_research_v1` is still the canonical project.
- The A-share path is now legacy and is no longer the default path.

## Exact Next Step
Repair `C:\Users\asus\Documents\Projects\BackTest\tests\test_platform_api.py`.

### Fix First
- Around line `528`: the `decision_trace` sample still has an unterminated string.
- The same area still contains several broken fixture strings and stale corrupted text.
- Replace those fixtures with clear plain strings. Do not keep corrupted text.

## Required Commands After The Fix
1. `python -m pytest tests/test_crypto_okx_contract.py tests/test_okx_provider.py tests/test_platform_api.py -q`
2. `python -m pytest tests/test_canonical_project_identity.py tests/test_strategy_visibility.py tests/test_config_manifest.py -q`
3. `python -m quant_mvp.cli doctor --project crypto_okx_research_v1`

## Do Not Do In The Next Chat
- Do not add new strategy branches.
- Do not start demo or live work.
- Do not open a new crypto repo.
- Do not restore A-share as the default path.
- Do not do broad cleanup of old memory files.

## Read These Files Before Coding
1. `C:\Users\asus\Documents\Projects\OpenClaw\docs\CURRENT_STRATEGIC_PLAN.md`
2. `C:\Users\asus\Documents\Projects\OpenClaw\docs\ACTIVE_EXECUTION_HANDOFF.md`
3. `C:\Users\asus\Documents\Projects\BackTest\memory\projects\crypto_okx_research_v1\HANDOFF_NEXT_CHAT.md`
4. `C:\Users\asus\Documents\Projects\BackTest\memory\projects\crypto_okx_research_v1\MIGRATION_PROMPT_NEXT_CHAT.md`
5. `C:\Users\asus\Documents\Projects\BackTest\docs\data_contracts\okx_public_market_data_v1.md`
6. `C:\Users\asus\Documents\Projects\BackTest\docs\experiments\crypto_okx_research_v1_phase0.md`

## Current Boundaries
- Research loop only. No demo or live.
- Only `BTC-USDT-SWAP` and `ETH-USDT-SWAP`.
- The first baseline is still a trend baseline.

## Final Reminder
After the test repair is done, review `C:\Users\asus\Documents\Projects\OpenClaw\docs\BUG_FIX_LEDGER.md` and count the verified bug fixes. Do not guess.
