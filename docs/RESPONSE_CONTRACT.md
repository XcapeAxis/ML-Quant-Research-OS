# Response Contract

## CHECKPOINT
- Default mode.
- Reply in exactly five sections: `Done`, `Not done`, `Research progress`, `Next recommendation`, `Subagent status`.
- Keep `Done` and `Not done` to exactly two bullet lines each.
- `Research progress` must include a Markdown table with the fixed dimensions `Data inputs`, `Strategy integrity`, `Validation stack`, `Promotion readiness`, and `Subagent effectiveness`.
- Each progress dimension must carry one conservative status label plus one `0/4` to `4/4` score.
- Keep the whole reply concise; with the required table it should usually stay under 30 lines.
- Do not inline long file contents or full diffs.
- Use paths plus the highest-signal command result only.
- Keep human-readable bullet text in Chinese for automation/user-facing summaries, while retaining the exact English section titles and progress dimension names for stable automation parsing.
- Do not expand every subagent history inside `CHECKPOINT`; keep only gate mode, max active count, lifecycle summary, and one brief justification when staying effectively OFF is the correct choice.

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
