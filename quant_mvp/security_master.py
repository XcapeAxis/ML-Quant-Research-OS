from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config
from .db import list_db_codes
from .project import resolve_project_paths
from .universe import load_universe_codes, save_universe_codes

CANONICAL_UNIVERSE_ID = "cn_a_mainboard_all_v1"
SECURITY_MASTER_FILENAME = "security_master.csv"
SECURITY_MASTER_MANIFEST_FILENAME = "security_master_manifest.json"
LEGACY_UNIVERSE_DIRNAME = "legacy_universe"

SECURITY_MASTER_COLUMNS = [
    "code",
    "name",
    "security_name",
    "security_full_name",
    "exchange",
    "board",
    "security_type",
    "share_class",
    "is_st",
    "st_label",
    "listing_date",
    "source",
    "classification_method",
]

EXCLUDED_SECURITY_TYPES = [
    "chinext",
    "star_market",
    "bse",
    "etf",
    "lof",
    "index_security",
    "b_share",
    "bond",
    "convertible_bond",
    "other_non_common_stock",
]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _normalize_code(code: Any) -> str:
    return str(code or "").strip().zfill(6)


def _is_mainboard_code(code: str) -> bool:
    value = _normalize_code(code)
    return not (
        value.startswith(("4", "8", "68", "300", "301"))
    )


def _exchange_from_code(code: str) -> str:
    value = _normalize_code(code)
    if value.startswith("6"):
        return "SSE"
    if value.startswith(("0", "001", "002", "003")):
        return "SZSE"
    return "UNKNOWN"


def _st_label(name: str | None) -> str:
    text = str(name or "").upper().replace(" ", "")
    if text.startswith("*ST"):
        return "*ST"
    if text.startswith("ST"):
        return "ST"
    return ""


def _bool_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values.fillna(False)
    return values.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=SECURITY_MASTER_COLUMNS)


def _finalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return _empty_frame()
    out = frame.copy()
    out["code"] = out["code"].map(_normalize_code)
    out["security_name"] = out.get("security_name", pd.Series([""] * len(out))).fillna("").astype(str)
    out["name"] = out.get("name", out["security_name"]).fillna("").astype(str)
    out["security_full_name"] = out.get("security_full_name", out["security_name"]).fillna("").astype(str)
    out["exchange"] = out.get("exchange", pd.Series(["UNKNOWN"] * len(out))).fillna("UNKNOWN").astype(str)
    out["board"] = out.get("board", pd.Series(["unknown"] * len(out))).fillna("unknown").astype(str)
    out["security_type"] = out.get("security_type", pd.Series(["common_stock"] * len(out))).fillna("common_stock").astype(str)
    out["share_class"] = out.get("share_class", pd.Series(["A"] * len(out))).fillna("A").astype(str)
    out["listing_date"] = out.get("listing_date", pd.Series([""] * len(out))).fillna("").astype(str)
    out["source"] = out.get("source", pd.Series(["unknown"] * len(out))).fillna("unknown").astype(str)
    out["classification_method"] = (
        out.get("classification_method", pd.Series(["unknown"] * len(out))).fillna("unknown").astype(str)
    )
    raw_is_st = out.get("is_st", pd.Series([False] * len(out)))
    out["is_st"] = _bool_series(raw_is_st) | out["security_name"].map(lambda value: bool(_st_label(value)))
    out["st_label"] = out.get("st_label", out["security_name"].map(_st_label)).fillna("").astype(str)
    out.loc[out["st_label"].eq(""), "st_label"] = out.loc[out["st_label"].eq(""), "security_name"].map(_st_label)
    out = out[SECURITY_MASTER_COLUMNS].drop_duplicates("code").sort_values("code").reset_index(drop=True)
    return out


def _fetch_remote_security_master() -> tuple[pd.DataFrame, str, list[str]]:
    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise RuntimeError("akshare is required to fetch the canonical security master") from exc

    sh = ak.stock_info_sh_name_code(symbol="\u4e3b\u677fA\u80a1").rename(
        columns={
            "\u8bc1\u5238\u4ee3\u7801": "code",
            "\u8bc1\u5238\u7b80\u79f0": "security_name",
            "\u8bc1\u5238\u5168\u79f0": "security_full_name",
            "\u4e0a\u5e02\u65e5\u671f": "listing_date",
        },
    )
    if sh is None or sh.empty:
        raise RuntimeError("SSE mainboard A-share list is empty")
    sh = sh[[column for column in ["code", "security_name", "security_full_name", "listing_date"] if column in sh.columns]].copy()
    sh["exchange"] = "SSE"
    sh["board"] = "mainboard"
    sh["security_type"] = "common_stock"
    sh["share_class"] = "A"
    sh["source"] = "akshare_exchange_lists"
    sh["classification_method"] = "exchange_metadata"

    sz = ak.stock_info_sz_name_code(symbol="A\u80a1\u5217\u8868").rename(
        columns={
            "\u677f\u5757": "board_cn",
            "A\u80a1\u4ee3\u7801": "code",
            "A\u80a1\u7b80\u79f0": "security_name",
            "A\u80a1\u4e0a\u5e02\u65e5\u671f": "listing_date",
        },
    )
    if sz is None or sz.empty:
        raise RuntimeError("SZSE A-share list is empty")
    if "board_cn" in sz.columns:
        sz = sz[sz["board_cn"].astype(str).str.strip().eq("\u4e3b\u677f")].copy()
    sz = sz[[column for column in ["code", "security_name", "listing_date"] if column in sz.columns]].copy()
    sz["security_full_name"] = sz["security_name"]
    sz["exchange"] = "SZSE"
    sz["board"] = "mainboard"
    sz["security_type"] = "common_stock"
    sz["share_class"] = "A"
    sz["source"] = "akshare_exchange_lists"
    sz["classification_method"] = "exchange_metadata"

    frame = pd.concat([sh, sz], ignore_index=True)
    frame["name"] = frame["security_name"]
    frame["st_label"] = frame["security_name"].map(_st_label)
    frame["is_st"] = frame["st_label"].ne("")
    frame = frame[frame["code"].map(_normalize_code).map(_is_mainboard_code)].copy()
    return _finalize_frame(frame), "akshare_exchange_lists", []


def _build_db_fallback(project: str, db_path: Path, freq: str) -> tuple[pd.DataFrame, str, list[str]]:
    codes = sorted(code for code in list_db_codes(db_path, freq=freq, data_mode="auto") if _is_mainboard_code(code))
    if not codes:
        raise RuntimeError("db fallback could not infer any mainboard symbols")
    frame = pd.DataFrame({"code": [_normalize_code(code) for code in codes]})
    frame["name"] = ""
    frame["security_name"] = ""
    frame["security_full_name"] = ""
    frame["exchange"] = frame["code"].map(_exchange_from_code)
    frame["board"] = "mainboard"
    frame["security_type"] = "common_stock"
    frame["share_class"] = "A"
    frame["is_st"] = False
    frame["st_label"] = ""
    frame["listing_date"] = ""
    frame["source"] = "db_fallback"
    frame["classification_method"] = "code_prefix_fallback"
    assumptions = [
        "Fallback source uses the local bars database because exchange metadata was unavailable.",
        "Fallback classification infers exchange from code prefix and assumes `security_type=common_stock`, `share_class=A`, `board=mainboard` only for codes that pass the mainboard prefix filter.",
        "Fallback mode keeps ST as an empty label when a reliable security name is unavailable.",
    ]
    return _finalize_frame(frame), "db_fallback", assumptions


def _fallback_from_universe_codes(project: str) -> tuple[pd.DataFrame, str, list[str]]:
    codes = [code for code in load_universe_codes(project) if _is_mainboard_code(code)]
    if not codes:
        raise RuntimeError("no existing universe codes available for fallback")
    frame = pd.DataFrame({"code": [_normalize_code(code) for code in codes]})
    frame["name"] = ""
    frame["security_name"] = ""
    frame["security_full_name"] = ""
    frame["exchange"] = frame["code"].map(_exchange_from_code)
    frame["board"] = "mainboard"
    frame["security_type"] = "common_stock"
    frame["share_class"] = "A"
    frame["is_st"] = False
    frame["st_label"] = ""
    frame["listing_date"] = ""
    frame["source"] = "universe_codes_fallback"
    frame["classification_method"] = "code_prefix_fallback"
    assumptions = [
        "Last-resort fallback rebuilds the master from existing universe codes when neither exchange metadata nor local DB metadata is available.",
        "This fallback is classification-only and should be replaced by an exchange metadata refresh before making strong research claims.",
    ]
    return _finalize_frame(frame), "universe_codes_fallback", assumptions


def _fallback_from_symbols_csv(symbols_path: Path) -> tuple[pd.DataFrame, str, list[str]]:
    frame = pd.read_csv(symbols_path, dtype={"code": str})
    if frame.empty or "code" not in frame.columns:
        raise RuntimeError("symbols.csv fallback is empty or missing code")
    working = pd.DataFrame({"code": frame["code"].map(_normalize_code)})
    working["name"] = frame.get("name", pd.Series([""] * len(frame))).fillna("").astype(str)
    working["security_name"] = frame.get("security_name", working["name"]).fillna("").astype(str)
    working["security_full_name"] = frame.get("security_full_name", working["security_name"]).fillna("").astype(str)
    working["exchange"] = frame.get("exchange", working["code"].map(_exchange_from_code)).fillna("UNKNOWN").astype(str)
    working["board"] = frame.get("board", pd.Series(["mainboard"] * len(frame))).fillna("mainboard").astype(str)
    working["security_type"] = (
        frame.get("security_type", pd.Series(["common_stock"] * len(frame))).fillna("common_stock").astype(str)
    )
    working["share_class"] = frame.get("share_class", pd.Series(["A"] * len(frame))).fillna("A").astype(str)
    working["is_st"] = frame.get("is_st", pd.Series([False] * len(frame)))
    working["st_label"] = frame.get("st_label", working["security_name"].map(_st_label)).fillna("").astype(str)
    working["listing_date"] = frame.get("listing_date", pd.Series([""] * len(frame))).fillna("").astype(str)
    working["source"] = "symbols_csv_fallback"
    working["classification_method"] = "local_metadata_fallback"
    assumptions = [
        "Fallback source uses local symbols.csv metadata because security_master.csv is unavailable.",
        "This fallback is acceptable for tests and temporary local recovery, but canonical active refresh should prefer exchange-derived security master metadata.",
    ]
    return _finalize_frame(working), str(symbols_path), assumptions


def load_security_master_frame(project: str, *, config_path: Path | None = None) -> tuple[pd.DataFrame, str]:
    _, paths = load_config(project, config_path=config_path)
    security_master_path = paths.meta_dir / SECURITY_MASTER_FILENAME
    if security_master_path.exists():
        frame = pd.read_csv(security_master_path, dtype={"code": str})
        return _finalize_frame(frame), str(security_master_path)
    symbols_path = paths.meta_dir / "symbols.csv"
    if symbols_path.exists():
        frame, source, _ = _fallback_from_symbols_csv(symbols_path)
        return frame, source
    fallback, source, _ = _fallback_from_universe_codes(project)
    return fallback, source


def _archive_existing_runtime_inputs(paths) -> dict[str, str]:
    legacy_dir = paths.meta_dir / LEGACY_UNIVERSE_DIRNAME
    archived: dict[str, str] = {}
    timestamp = _timestamp_slug()

    if paths.universe_path.exists():
        target = legacy_dir / f"legacy_universe_codes_{timestamp}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths.universe_path, target)
        archived["legacy_universe_codes_path"] = str(target)

    symbols_path = paths.meta_dir / "symbols.csv"
    if symbols_path.exists():
        target = legacy_dir / f"legacy_symbols_{timestamp}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(symbols_path, target)
        archived["legacy_symbols_path"] = str(target)

    security_master_path = paths.meta_dir / SECURITY_MASTER_FILENAME
    if security_master_path.exists():
        target = legacy_dir / f"legacy_security_master_{timestamp}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(security_master_path, target)
        archived["legacy_security_master_path"] = str(target)

    return archived


@dataclass(frozen=True)
class SecurityMasterBuildResult:
    project: str
    universe_id: str
    generated_at: str
    source: str
    assumptions: list[str]
    excluded_security_types: list[str]
    count: int
    exchange_counts: dict[str, int]
    board_counts: dict[str, int]
    st_count: int
    security_master_path: str
    symbols_path: str
    universe_path: str
    manifest_path: str
    archive_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_security_master(
    project: str,
    *,
    config_path: Path | None = None,
    archive_existing: bool = True,
) -> SecurityMasterBuildResult:
    cfg, paths = load_config(project, config_path=config_path)
    paths.ensure_dirs()
    archive_paths = _archive_existing_runtime_inputs(paths) if archive_existing else {}

    assumptions: list[str] = []
    try:
        frame, source, assumptions = _fetch_remote_security_master()
    except Exception as exc:
        try:
            frame, source, assumptions = _build_db_fallback(
                project=project,
                db_path=Path(str(cfg["db_path"])),
                freq=str(cfg["freq"]),
            )
            assumptions = [f"Remote exchange metadata failed: {exc}", *assumptions]
        except Exception:
            frame, source, assumptions = _fallback_from_universe_codes(project)
            assumptions = [f"Remote exchange metadata failed: {exc}", *assumptions]

    frame = _finalize_frame(frame)
    frame = frame[
        frame["exchange"].isin({"SSE", "SZSE"})
        & frame["board"].str.lower().eq("mainboard")
        & frame["security_type"].str.lower().eq("common_stock")
        & frame["share_class"].str.upper().eq("A")
    ].copy()
    if frame.empty:
        raise RuntimeError("canonical security master is empty after filtering")

    security_master_path = paths.meta_dir / SECURITY_MASTER_FILENAME
    symbols_path = paths.meta_dir / "symbols.csv"
    manifest_path = paths.meta_dir / SECURITY_MASTER_MANIFEST_FILENAME

    frame.to_csv(security_master_path, index=False, encoding="utf-8-sig")
    frame.to_csv(symbols_path, index=False, encoding="utf-8-sig")
    save_universe_codes(project=project, codes=frame["code"].tolist())

    generated_at = _utc_now()
    exchange_counts = {str(key): int(value) for key, value in frame["exchange"].value_counts().sort_index().items()}
    board_counts = {str(key): int(value) for key, value in frame["board"].value_counts().sort_index().items()}
    payload = {
        "project": project,
        "universe_id": CANONICAL_UNIVERSE_ID,
        "generated_at": generated_at,
        "source": source,
        "count": int(len(frame)),
        "exchange_counts": exchange_counts,
        "board_counts": board_counts,
        "st_count": int(frame["is_st"].sum()),
        "assumptions": assumptions,
        "excluded_security_types": EXCLUDED_SECURITY_TYPES,
        "security_master_path": str(security_master_path),
        "symbols_path": str(symbols_path),
        "universe_path": str(paths.universe_path),
        "archive_paths": archive_paths,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    return SecurityMasterBuildResult(
        project=project,
        universe_id=CANONICAL_UNIVERSE_ID,
        generated_at=generated_at,
        source=source,
        assumptions=assumptions,
        excluded_security_types=list(EXCLUDED_SECURITY_TYPES),
        count=int(len(frame)),
        exchange_counts=exchange_counts,
        board_counts=board_counts,
        st_count=int(frame["is_st"].sum()),
        security_master_path=str(security_master_path),
        symbols_path=str(symbols_path),
        universe_path=str(paths.universe_path),
        manifest_path=str(manifest_path),
        archive_paths=dict(archive_paths),
    )
