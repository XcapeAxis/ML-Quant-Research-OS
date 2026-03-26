# Research Iteration Loop

Use this repo-local skill when an automation needs one bounded run that can iterate multiple times without becoming an open-ended agent session.

## What It Does
- Reads tracked project memory first.
- Runs `.venv\Scripts\python.exe -m quant_mvp iterative_run --project <project> --config <config> --target-iterations 3 --max-iterations 5 --format checkpoint` on Windows when the repo virtualenv exists.
- Reassesses repo truth before each iteration.
- Keeps subagents effectively OFF unless the tracked task structure clearly justifies expansion.
- Writes compact loop state back into tracked memory and stores the full run payload under `artifacts/projects/<project>/automation_runs/`.

## Guardrails
- Stop immediately on no verified progress, repeated blocker escalation, failure-scope expansion, insufficient context, or unsafe worktree state.
- When the same blocker appears twice, switch the next recommendation to finer root-cause diagnosis; on the third appearance, escalate and stop automatic retries.
- Do not widen scope just to consume more iterations.
- Keep the final automation reply in `CHECKPOINT` form: `Done`, `Evidence`, `Next action`, `Subagent status`.
