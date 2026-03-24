# Tooling Ledger

## 2026-03-24
- No new runtime dependency was introduced for this refactor.
- The repo now uses a provider abstraction over AKShare rather than embedding AKShare response assumptions directly inside strategy code.
- A YAML allowlist file was added for the agent control plane, parsed with a small in-repo reader to avoid adding a new parser dependency.
