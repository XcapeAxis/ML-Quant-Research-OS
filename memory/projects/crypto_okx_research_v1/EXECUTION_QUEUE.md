# Execution Queue

| Task ID | Title | Impact | Risk | Prerequisite | Status | Owner | Success Condition | Stop Condition |
|---|---|---|---|---|---|---|---|---|
| materialize_phase0_universe | Materialize the OKX phase-0 universe file | high | low | The universe contract exists. | done | main | universe_codes.txt matches the frozen contract. | The universe contract is missing or invalid. |
| recover_okx_bars | Load OKX bars for the frozen universe | high | medium | Universe file exists and the exchange endpoints are reachable. | ready | main | doctor reports usable local bars for the frozen OKX universe. | Data import still produces zero usable bars for the frozen universe. |
| refresh_research_audit | Refresh research audit after data truth changes | medium | low | Universe and doctor truth are up to date. | queued | main | audit restates the bounded next step without legacy leakage. | audit adds no new boundary information. |
| bounded_agent_cycle | Run one dry-run research cycle | medium | medium | Doctor and audit no longer block on missing research inputs. | blocked | main | dry-run adds bounded evidence instead of repeating setup work. | dry-run only repeats the same blocker. |
