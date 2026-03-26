# Response Contract

## CHECKPOINT
- Default mode.
- Reply in exactly four sections: `Done`, `Not done`, `Next recommendation`, `Subagent status`.
- Keep the whole reply under 20 lines.
- Do not inline long file contents or full diffs.
- Use paths plus the highest-signal command result only.
- Keep human-readable bullet text in Chinese for automation/user-facing summaries.
- Do not expand every subagent history inside `CHECKPOINT`; keep only gate mode, max active count, lifecycle summary, and the next merge/retire action when it matters.

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
