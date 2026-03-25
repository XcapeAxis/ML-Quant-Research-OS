# Data Pipeline

## Layers
1. Raw
   - Source provider fetches bars into `bars`.
   - The current AKShare provider prefers the Tencent daily-history endpoint and falls back to Eastmoney when Tencent is unavailable.
   - Symbols are normalized to six-digit A-share codes.
2. Cleaned
   - `bars_clean` is rebuilt from raw bars with explicit issue tracking.
   - Invalid datetime, duplicate rows, invalid prices, and invalid volume are removed or repaired with logs.
3. Validated
   - Validation reports check coverage, duplicates, zero-volume rows, suspension proxies, and limit-lock proxies.
   - Project reports are written to `data/projects/<project>/meta/DATA_QUALITY_REPORT.md`.

## Contracts
- Every update writes the provider identity and date range into the manifest.
- Every clean run writes summary JSON/CSV plus a Markdown report.
- Validation reports are project-scoped, not global.
- Future paid providers must implement the provider interface instead of patching scripts directly.
