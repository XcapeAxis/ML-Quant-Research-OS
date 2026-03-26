# Research Iteration Loop

Use this repo-local skill when an automation needs one bounded run that can iterate multiple times without becoming an open-ended agent session.

## What It Does
- Reads tracked project memory first.
- Runs `.venv\Scripts\python.exe -m quant_mvp iterative_run --project <project> --config <config> --target-productive-minutes 40 --target-iterations 4 --max-iterations 6 --min-substantive-actions 2 --target-substantive-actions 3 --clarify-only-limit 1 --format checkpoint` on Windows when the repo virtualenv exists.
- Reassesses repo truth before each iteration.
- Builds one run-local context cache plus a tracked `EXECUTION_QUEUE.md`, so the run can push several small closed loops before writing back durable memory.
- Dynamically reconciles subagents inside the loop: retire/archive finished work, add replacements only when newly justified, and never exceed the configured hard limit.
- Writes compact loop state back into tracked memory with Chinese human-readable summaries, while storing the full run payload under `artifacts/projects/<project>/automation_runs/`.
- Emits a mandatory `Research progress` snapshot on every completed run using the fixed five-dimension Phase-1 scoring model.

## Guardrails
- Stop on repeated blocker escalation, failure-scope expansion, insufficient context, unsafe worktree state, or two consecutive iterations without effective progress.
- When the same blocker appears twice, switch the next recommendation to finer root-cause diagnosis; on the third appearance, escalate and stop automatic retries.
- Do not widen scope just to consume more iterations.
- Keep the final automation reply in `CHECKPOINT` form: `Done`, `Not done`, `Research progress`, `Next recommendation`, `Subagent status`.
- The `Research progress` table must always contain the exact dimensions `Data inputs`, `Strategy integrity`, `Validation stack`, `Promotion readiness`, and `Subagent effectiveness`, each with a conservative `0-4` score and controlled status label.
- When the run materially changes project truth, write the same progress snapshot back into tracked memory, including `PROJECT_STATE.md`, `RESEARCH_MEMORY.md`, `VERIFY_LAST.md`, `HANDOFF_NEXT_CHAT.md`, `MIGRATION_PROMPT_NEXT_CHAT.md`, and `SESSION_STATE.json`.
- Keep user-facing summaries and tracked long-term memory in Chinese; machine-readable state may stay language-neutral.
