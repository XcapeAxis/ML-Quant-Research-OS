# scripts Scope

- Scripts orchestrate library code only.
- Do not embed strategy defaults or duplicate selection logic here.
- Scripts should write explicit artifacts and manifest entries for reproducibility.
- Durable memory writes must go through the tracked memory layer rather than ad-hoc files in `data/`.
