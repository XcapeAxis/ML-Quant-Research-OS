# Response Contract

## CHECKPOINT
- Default mode.
- Reply in exactly three sections: `Done`, `Evidence`, `Next action`.
- Keep the whole reply under 20 lines.
- Do not inline long file contents or full diffs.
- Use paths plus the highest-signal command result only.

## EVIDENCE
- Use only when the user explicitly asks to verify one specific claim or one specific file/command/result.
- Keep scope narrow; do not expand to adjacent evidence unless the user asks.

## FORENSICS_FULL
- Use only when the user explicitly asks for a full evidence pack, full forensics, or `FULL EVIDENCE`.
- Large evidence bundles are opt-in, not the default.

## Memory Boundary Reminder
- Durable tracked memory belongs under `memory/projects/<project>/`.
- Runtime/high-noise outputs belong under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
