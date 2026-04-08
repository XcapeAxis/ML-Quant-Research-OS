from __future__ import annotations

import json
from pathlib import Path

from .config import load_config
from .project import find_repo_root
from .project import resolve_project_paths


def load_universe_codes(project: str) -> list[str]:
    paths = resolve_project_paths(project)
    if not paths.universe_path.exists():
        raise FileNotFoundError(
            f"Universe file not found: {paths.universe_path}. Run scripts/steps/10_symbols.py first.",
        )
    with open(paths.universe_path, "r", encoding="utf-8") as handle:
        codes = [line.strip() for line in handle if line.strip()]
    return sorted(set(codes))


def save_universe_codes(project: str, codes: list[str]) -> Path:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()
    with open(paths.universe_path, "w", encoding="utf-8") as handle:
        for code in sorted(set(codes)):
            text = str(code).strip()
            if not text:
                continue
            normalized = text.zfill(6) if text.isdigit() else text
            handle.write(f"{normalized}\n")
    return paths.universe_path


def materialize_universe_from_project_contract(project: str, *, config_path: Path | None = None) -> dict[str, object]:
    cfg, paths = load_config(project, config_path=config_path)
    universe_policy = dict(cfg.get("universe_policy", {}) or {})
    definitions_dir = Path(str(universe_policy.get("definitions_dir") or "configs/universes"))
    research_profile = str(
        universe_policy.get("research_profile")
        or universe_policy.get("canonical_universe_id")
        or ""
    ).strip()
    if not research_profile:
        raise ValueError("universe_policy must define research_profile or canonical_universe_id")

    repo_root = find_repo_root()
    contract_path = (repo_root / definitions_dir / f"{research_profile}.yaml").resolve()
    if not contract_path.exists():
        raise FileNotFoundError(f"Universe contract not found: {contract_path}")

    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    codes = (
        payload.get("symbols")
        or payload.get("instrument_ids")
        or payload.get("codes")
        or payload.get("default_symbols")
        or []
    )
    normalized_codes = [str(item).strip() for item in codes if str(item).strip()]
    if not normalized_codes:
        raise ValueError(f"Universe contract has no symbols/instrument_ids/codes: {contract_path}")

    universe_path = save_universe_codes(project, normalized_codes)
    return {
        "project": paths.project,
        "research_profile": research_profile,
        "contract_path": str(contract_path),
        "universe_path": str(universe_path),
        "count": len(sorted(set(normalized_codes))),
        "symbols": sorted(set(normalized_codes)),
    }
