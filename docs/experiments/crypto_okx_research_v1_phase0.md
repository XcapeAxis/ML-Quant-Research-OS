# crypto_okx_research_v1 Phase 0 Experiment Spec

## Goal

Prove that the research loop works before any demo or live execution work starts.

## Required Bundle

Every phase-0 experiment should carry:

- hypothesis
- dataset scope
- bar frequency
- fee and slippage assumptions
- funding treatment
- evaluation window
- walk-forward rule
- postmortem rule

## Minimum Evaluation Questions

1. Is the result better than a simple baseline?
2. Does it survive a small parameter change?
3. Does it survive a walk-forward split?
4. Does the result still look acceptable after fees and slippage?
5. If swaps are involved, was funding handled or explicitly excluded?

## Hard Fail Conditions

The experiment fails phase 0 if any of these are true:

- sample is too short
- fees are missing
- slippage is missing
- funding is ignored when it matters
- walk-forward is absent
- result is strong only in-sample
- conclusion is stronger than evidence

## Promotion Rule

A phase-0 experiment may become a promotion candidate only after:

- `solution-scout` comparison is recorded
- `risk-review` says pass or cautious-pass
- decision refs are written into recall and postmortem memory

## Current Default

The current default project for this spec is `crypto_okx_research_v1`.
