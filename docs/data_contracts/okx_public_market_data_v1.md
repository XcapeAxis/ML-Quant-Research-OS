# OKX Public Market Data Contract v1

## Purpose

This contract defines the minimum public market data shape for `crypto_okx_research_v1`.

This is a research contract, not an execution contract.

## Scope

- exchange: `OKX`
- market: `crypto`
- phase: `phase-0-backtest-first`
- access mode: public REST / public WebSocket only

## Required Entities

### 1. Instrument metadata

Each instrument record should at least include:

- `instId`
- `instType`
- `baseCcy`
- `quoteCcy`
- `settleCcy`
- `ctVal`
- `ctMult`
- `tickSz`
- `lotSz`
- `state`

### 2. OHLCV bars

Each bar should normalize to:

- `symbol`
- `datetime`
- `freq`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `quote_volume`
- `trades`

### 3. Funding rate

For perpetual or swap products, funding rows should at least include:

- `symbol`
- `funding_time`
- `funding_rate`
- `next_funding_rate` if available

### 4. Fee model

The research layer must carry:

- maker fee assumption
- taker fee assumption
- slippage assumption
- whether the assumption came from public docs or local override

## Phase-0 Rule

If any experiment ignores:

- fee assumptions
- contract specs
- funding impact when relevant

then it cannot pass `risk-review`.

## Out of Scope

- order placement
- account balances
- live execution state
- cross-exchange routing
