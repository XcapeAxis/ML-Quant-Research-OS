# Response Contract

## CHECKPOINT
- Default mode.
- Reply in exactly four sections: `Done`, `Evidence`, `Next action`, `Subagent status`.
- `Done` must stay strategy-centered: one bullet for `系统推进`, one bullet for `策略推进`.
- If the run did not advance any concrete strategy candidate, the `策略推进` bullet must state that explicitly and explain why.
- `Evidence` must show the current primary / secondary / blocked / rejected / promoted strategy snapshot in plain Chinese, plus the current blocker.
- Keep the whole reply concise and direct; avoid abstract orchestration language unless it is immediately explained in everyday Chinese.
- Do not inline long file contents or full diffs.
- Use paths plus the highest-signal command result only.
- Keep human-readable bullet text in Chinese for automation/user-facing summaries, while retaining the exact English section titles for stable automation parsing.
- Do not expand every subagent history inside `CHECKPOINT`; keep only active research / infrastructure split, lifecycle summary, and one brief justification when staying effectively OFF is the correct choice.

## EVIDENCE
- Use only when the user explicitly asks to verify one specific claim or one specific file/command/result.
- Keep scope narrow; do not expand to adjacent evidence unless the user asks.

## FORENSICS_FULL
- Use only when the user explicitly asks for a full evidence pack, full forensics, or `FULL EVIDENCE`.
- Large evidence bundles are opt-in, not the default.

## Memory Boundary Reminder
- Durable tracked memory belongs under `memory/projects/<project>/`.
- Runtime/high-noise outputs belong under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
- Subagent runtime payloads belong under `artifacts/projects/<project>/subagents/<subagent_id>/`.
