from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config
from .memory.ledger import stable_hash
from .project import find_repo_root
from .security_master import CANONICAL_UNIVERSE_ID, load_security_master_frame
from .universe import load_universe_codes


def _normalize_code(code: Any) -> str:
    return str(code).strip().zfill(6)


def _looks_like_mainboard(code: str) -> bool:
    value = _normalize_code(code)
    return not (
        value.startswith("4")
        or value.startswith("8")
        or value.startswith("68")
        or value.startswith("300")
        or value.startswith("301")
    )


def _is_st_like(name: str | None) -> bool:
    text = str(name or "").upper()
    return "ST" in text or "*" in text or "退" in str(name or "")


def _profile_dir(root: Path) -> Path:
    return root / "configs" / "universes"


@dataclass(frozen=True)
class UniverseProfileDefinition:
    profile_id: str
    display_name: str
    description: str
    board_scope: str = "mainboard_a_share"
    include_st: bool = True
    source_kind: str = "project_symbols_csv"
    allowed_exchanges: tuple[str, ...] = ("SSE", "SZSE")
    allowed_boards: tuple[str, ...] = ("mainboard",)
    allowed_security_types: tuple[str, ...] = ("common_stock",)
    allowed_share_classes: tuple[str, ...] = ("A",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UniverseProfileMaterialization:
    profile_id: str
    display_name: str
    description: str
    source_id: str
    source_kind: str
    source_path: str
    artifact_path: str
    codes: list[str]
    source_count: int
    included_count: int
    source_st_count: int
    included_st_count: int
    board_scope: str
    include_st: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_universe_profile_definition(
    profile_name: str,
    *,
    repo_root: Path | None = None,
) -> UniverseProfileDefinition:
    root = find_repo_root(repo_root)
    path = _profile_dir(root) / f"{profile_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Universe profile not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return UniverseProfileDefinition(
        profile_id=str(payload.get("profile_id") or profile_name),
        display_name=str(payload.get("display_name") or profile_name),
        description=str(payload.get("description") or ""),
        board_scope=str(payload.get("board_scope") or "mainboard_a_share"),
        include_st=bool(payload.get("include_st", True)),
        source_kind=str(payload.get("source_kind") or "project_symbols_csv"),
        allowed_exchanges=tuple(str(item) for item in payload.get("allowed_exchanges", ["SSE", "SZSE"])),
        allowed_boards=tuple(str(item) for item in payload.get("allowed_boards", ["mainboard"])),
        allowed_security_types=tuple(str(item) for item in payload.get("allowed_security_types", ["common_stock"])),
        allowed_share_classes=tuple(str(item) for item in payload.get("allowed_share_classes", ["A"])),
    )


def load_universe_profile_catalog(
    *,
    repo_root: Path | None = None,
) -> dict[str, UniverseProfileDefinition]:
    root = find_repo_root(repo_root)
    catalog: dict[str, UniverseProfileDefinition] = {}
    for path in sorted(_profile_dir(root).glob("*.yaml")):
        definition = load_universe_profile_definition(path.stem, repo_root=root)
        catalog[definition.profile_id] = definition
    return catalog


def _load_symbols_frame(project: str, *, config_path: Path | None = None) -> tuple[pd.DataFrame, str]:
    frame, source_path = load_security_master_frame(project, config_path=config_path)
    if not frame.empty:
        frame = frame.copy()
        frame["code"] = frame["code"].astype(str).map(_normalize_code)
        frame["name"] = frame.get("name", frame.get("security_name", pd.Series([""] * len(frame)))).fillna("").astype(str)
        raw_is_st = frame.get("is_st", pd.Series([False] * len(frame)))
        if raw_is_st.dtype == bool:
            frame["is_st"] = raw_is_st.fillna(False)
        else:
            frame["is_st"] = raw_is_st.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})
        frame["board"] = frame.get("board", pd.Series([""] * len(frame))).fillna("").astype(str)
        frame["exchange"] = frame.get("exchange", pd.Series(["UNKNOWN"] * len(frame))).fillna("UNKNOWN").astype(str)
        frame["security_type"] = (
            frame.get("security_type", pd.Series(["common_stock"] * len(frame))).fillna("common_stock").astype(str)
        )
        frame["share_class"] = frame.get("share_class", pd.Series(["A"] * len(frame))).fillna("A").astype(str)
        return (
            frame[
                ["code", "name", "is_st", "board", "exchange", "security_type", "share_class"]
            ].drop_duplicates("code"),
            source_path,
        )

    codes = load_universe_codes(project)
    frame = pd.DataFrame(
        {
            "code": [_normalize_code(code) for code in codes],
            "name": [""] * len(codes),
            "is_st": [False] * len(codes),
            "board": ["mainboard" if _looks_like_mainboard(code) else "unknown" for code in codes],
            "exchange": [("SSE" if str(code).startswith("6") else "SZSE") for code in codes],
            "security_type": ["common_stock"] * len(codes),
            "share_class": ["A"] * len(codes),
        },
    )
    return frame, "universe_codes_fallback"


def materialize_universe_profile(
    project: str,
    profile_name: str,
    *,
    config_path: Path | None = None,
    repo_root: Path | None = None,
) -> UniverseProfileMaterialization:
    root = find_repo_root(repo_root)
    cfg, paths = load_config(project, config_path=config_path)
    del cfg
    definition = load_universe_profile_definition(profile_name, repo_root=root)
    frame, source_path = _load_symbols_frame(project, config_path=config_path)
    frame = frame.copy()
    frame["code"] = frame["code"].map(_normalize_code)
    frame["is_st"] = frame["is_st"].astype(bool) | frame["name"].map(_is_st_like)
    frame["board"] = frame["board"].fillna("").astype(str)
    frame["exchange"] = frame.get("exchange", pd.Series(["UNKNOWN"] * len(frame))).fillna("UNKNOWN").astype(str)
    frame["security_type"] = frame.get("security_type", pd.Series(["common_stock"] * len(frame))).fillna("common_stock").astype(str)
    frame["share_class"] = frame.get("share_class", pd.Series(["A"] * len(frame))).fillna("A").astype(str)
    if definition.board_scope == "mainboard_a_share":
        frame = frame[
            frame["board"].str.lower().eq("mainboard") | frame["code"].map(_looks_like_mainboard)
        ].copy()
    if definition.allowed_exchanges:
        frame = frame[frame["exchange"].isin(set(definition.allowed_exchanges))].copy()
    if definition.allowed_boards:
        frame = frame[frame["board"].str.lower().isin({item.lower() for item in definition.allowed_boards})].copy()
    if definition.allowed_security_types:
        frame = frame[
            frame["security_type"].str.lower().isin({item.lower() for item in definition.allowed_security_types})
        ].copy()
    if definition.allowed_share_classes:
        frame = frame[
            frame["share_class"].str.upper().isin({item.upper() for item in definition.allowed_share_classes})
        ].copy()
    if not definition.include_st:
        frame = frame[~frame["is_st"]].copy()

    codes = sorted(frame["code"].dropna().map(_normalize_code).unique().tolist())
    source_frame, _ = _load_symbols_frame(project, config_path=config_path)
    source_frame = source_frame.copy()
    source_frame["code"] = source_frame["code"].map(_normalize_code)
    source_frame["is_st"] = source_frame["is_st"].astype(bool) | source_frame["name"].map(_is_st_like)
    source_frame["board"] = source_frame["board"].fillna("").astype(str)
    source_frame["exchange"] = source_frame.get("exchange", pd.Series(["UNKNOWN"] * len(source_frame))).fillna("UNKNOWN").astype(str)
    source_frame["security_type"] = (
        source_frame.get("security_type", pd.Series(["common_stock"] * len(source_frame))).fillna("common_stock").astype(str)
    )
    source_frame["share_class"] = source_frame.get("share_class", pd.Series(["A"] * len(source_frame))).fillna("A").astype(str)
    if definition.board_scope == "mainboard_a_share":
        source_frame = source_frame[
            source_frame["board"].str.lower().eq("mainboard") | source_frame["code"].map(_looks_like_mainboard)
        ].copy()
    if definition.allowed_exchanges:
        source_frame = source_frame[source_frame["exchange"].isin(set(definition.allowed_exchanges))].copy()
    if definition.allowed_boards:
        source_frame = source_frame[
            source_frame["board"].str.lower().isin({item.lower() for item in definition.allowed_boards})
        ].copy()
    if definition.allowed_security_types:
        source_frame = source_frame[
            source_frame["security_type"].str.lower().isin({item.lower() for item in definition.allowed_security_types})
        ].copy()
    if definition.allowed_share_classes:
        source_frame = source_frame[
            source_frame["share_class"].str.upper().isin({item.upper() for item in definition.allowed_share_classes})
        ].copy()

    artifact_dir = paths.meta_dir / "universe_profiles"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_payload = {
        "project": paths.project,
        "profile": definition.to_dict(),
        "source_path": source_path,
        "codes": codes,
        "source_count": int(source_frame["code"].nunique()),
        "included_count": len(codes),
        "source_st_count": int(source_frame["is_st"].sum()),
        "included_st_count": int(frame["is_st"].sum()) if "is_st" in frame.columns else 0,
    }
    payload_hash = stable_hash(artifact_payload)
    source_id = f"universe-profile:{definition.profile_id}:{payload_hash[:12]}"
    if definition.profile_id == CANONICAL_UNIVERSE_ID:
        source_id = f"{CANONICAL_UNIVERSE_ID}:{payload_hash[:12]}"
    artifact_payload["source_id"] = source_id
    artifact_path = artifact_dir / f"{definition.profile_id}.json"
    artifact_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2).rstrip() + "\n",
        encoding="utf-8",
    )

    return UniverseProfileMaterialization(
        profile_id=definition.profile_id,
        display_name=definition.display_name,
        description=definition.description,
        source_id=source_id,
        source_kind=definition.source_kind,
        source_path=source_path,
        artifact_path=str(artifact_path),
        codes=codes,
        source_count=int(source_frame["code"].nunique()),
        included_count=len(codes),
        source_st_count=int(source_frame["is_st"].sum()),
        included_st_count=int(frame["is_st"].sum()) if "is_st" in frame.columns else 0,
        board_scope=definition.board_scope,
        include_st=definition.include_st,
    )
