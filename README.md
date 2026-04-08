# BackTest Research Kernel

This repo is no longer an A-share-first research OS.

Its new role is a market-agnostic research kernel.  
The current mainline is:

- project: `crypto_okx_research_v1`
- market: `crypto`
- exchange: `OKX`
- phase: `Backtest First`

The old A-share branch stays here as a legacy reference:

- legacy project: `as_share_research_v1`
- legacy alias: `2026Q1_limit_up`
- status: archive and comparison only

## What This Repo Is For Now

Phase 0 is deliberately narrow:

- prove the research loop
- keep decisions, recall, and postmortems durable
- define data contracts before data plumbing grows
- keep live scope at `none`

This repo is **not** currently:

- a live trading system
- a broker execution engine
- a multi-exchange automation platform
- a promise of profitable strategy output

## Current Mainline

The current mainline project is `crypto_okx_research_v1`.

Its minimum kernel surfaces are:

- project config: [C:\Users\asus\Documents\Projects\BackTest\configs\projects\crypto_okx_research_v1.json](C:\Users\asus\Documents\Projects\BackTest\configs\projects\crypto_okx_research_v1.json)
- universe contract: [C:\Users\asus\Documents\Projects\BackTest\configs\universes\okx_crypto_linear_swap_v1.yaml](C:\Users\asus\Documents\Projects\BackTest\configs\universes\okx_crypto_linear_swap_v1.yaml)
- data contract: [C:\Users\asus\Documents\Projects\BackTest\docs\data_contracts\okx_public_market_data_v1.md](C:\Users\asus\Documents\Projects\BackTest\docs\data_contracts\okx_public_market_data_v1.md)
- phase-0 experiment spec: [C:\Users\asus\Documents\Projects\BackTest\docs\experiments\crypto_okx_research_v1_phase0.md](C:\Users\asus\Documents\Projects\BackTest\docs\experiments\crypto_okx_research_v1_phase0.md)

## Current Rules

- Backtest First.
- Crypto First.
- OKX First.
- Public market data first.
- No live trading in this phase.
- No widening to demo or live without explicit risk review.

## Core Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Bootstrap tracked memory for the active project:

```bash
python -m quant_mvp memory_bootstrap --project crypto_okx_research_v1
```

Check whether the project contract is wired enough to proceed:

```bash
python -m quant_mvp doctor --project crypto_okx_research_v1
```

Refresh tracked memory after any contract or state change:

```bash
python -m quant_mvp memory_sync --project crypto_okx_research_v1
```

Run one bounded dry-run research cycle:

```bash
python -m quant_mvp agent_cycle --project crypto_okx_research_v1 --dry-run
```

Run the repo audit:

```bash
python -m quant_mvp research_audit --project crypto_okx_research_v1
```

## Legacy A-Share Path

The A-share path remains in this repo for:

- archive comparison
- migration notes
- old experiment context
- old tooling reference

It is no longer the default mainline.

If you need it, call it explicitly:

```bash
python -m quant_mvp memory_bootstrap --project as_share_research_v1
```

## Memory and Audit

Main tracked memory for the active mainline lives under:

- [C:\Users\asus\Documents\Projects\BackTest\memory\projects\crypto_okx_research_v1](C:\Users\asus\Documents\Projects\BackTest\memory\projects\crypto_okx_research_v1)

Key system docs remain:

- [C:\Users\asus\Documents\Projects\BackTest\docs\SYSTEM_BLUEPRINT.md](C:\Users\asus\Documents\Projects\BackTest\docs\SYSTEM_BLUEPRINT.md)
- [C:\Users\asus\Documents\Projects\BackTest\docs\SYSTEM_AUDIT.md](C:\Users\asus\Documents\Projects\BackTest\docs\SYSTEM_AUDIT.md)
- [C:\Users\asus\Documents\Projects\BackTest\docs\DECISION_LOG.md](C:\Users\asus\Documents\Projects\BackTest\docs\DECISION_LOG.md)

## What Not To Build Yet

- full live execution
- multi-exchange abstraction
- new shell UI
- large dashboard work
- extra permanent agent roles
