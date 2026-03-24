from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.db import list_db_codes
from quant_mvp.manifest import update_run_manifest
from quant_mvp.networking import NetworkRuntimeConfig
from quant_mvp.universe import save_universe_codes


def _board(code: str) -> str:
    value = str(code).zfill(6)
    if value.startswith(("688", "689")):
        return "star"
    if value.startswith(("300", "301")):
        return "chinext"
    if value.startswith(("8", "4")):
        return "bse"
    if value.startswith(("0", "6")):
        return "mainboard"
    return "unknown"


def _is_st(name: str) -> bool:
    text = str(name or "").upper()
    return "ST" in text or "退" in text


def _valid_mainboard(code: str) -> bool:
    return _board(code) == "mainboard"


def _symbols_output_path(paths) -> Path:
    output = paths.meta_dir / "symbols.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _finalize_symbols(project: str, df: pd.DataFrame) -> tuple[Path, Path, int]:
    from quant_mvp.project import resolve_project_paths

    paths = resolve_project_paths(project)
    symbols_path = _symbols_output_path(paths)
    df[["code", "name", "is_st", "board"]].to_csv(symbols_path, index=False, encoding="utf-8-sig")
    universe_path = save_universe_codes(project=project, codes=df["code"].tolist())
    return symbols_path, universe_path, int(df.shape[0])


def _build_symbols_from_db(project: str, db_path: Path, freq: str, target_size: int | None = None) -> tuple[Path, Path, int] | None:
    if not db_path.exists():
        return None
    codes = sorted(code for code in list_db_codes(db_path, freq=freq, data_mode="auto") if _valid_mainboard(code))
    if not codes:
        return None
    if target_size and target_size > 0 and len(codes) > target_size:
        codes = codes[:target_size]
    frame = pd.DataFrame(
        {
            "code": codes,
            "name": [""] * len(codes),
            "is_st": [False] * len(codes),
            "board": ["mainboard"] * len(codes),
        },
    )
    return _finalize_symbols(project, frame)


def _build_symbols_from_akshare(project: str, target_size: int | None = None) -> tuple[Path, Path, int]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required when the universe cannot be inferred from the local DB") from exc

    frame = ak.stock_info_a_code_name()
    if frame is None or frame.empty:
        raise RuntimeError("akshare returned an empty symbol universe")
    frame = frame.rename(columns={"code": "code", "name": "name"})[["code", "name"]].copy()
    frame["code"] = frame["code"].astype(str).str.zfill(6)
    frame["board"] = frame["code"].apply(_board)
    frame["is_st"] = frame["name"].apply(_is_st)
    frame = frame[(frame["board"] == "mainboard") & (~frame["is_st"])]
    frame = frame.drop_duplicates("code").sort_values("code").reset_index(drop=True)
    if target_size and target_size > 0 and len(frame) > target_size:
        frame = frame.head(target_size).copy()
    return _finalize_symbols(project, frame)


def _fetch_sse_mainboard_symbols(_network_cfg: NetworkRuntimeConfig) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required to fetch the exchange universe") from exc
    frame = ak.stock_info_sh_name_code(symbol="主板A股")
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["code", "name"])
    rename_map = {"证券代码": "code", "公司简称（英文）": "name", "证券简称": "name"}
    frame = frame.rename(columns=rename_map)
    return frame[[col for col in ["code", "name"] if col in frame.columns]].copy()


def _fetch_szse_a_symbols(_network_cfg: NetworkRuntimeConfig) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required to fetch the exchange universe") from exc
    frame = ak.stock_info_sz_name_code(symbol="A股列表")
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["code", "name"])
    rename_map = {"A股代码": "code", "A股简称": "name", "证券代码": "code", "证券简称": "name"}
    frame = frame.rename(columns=rename_map)
    return frame[[col for col in ["code", "name"] if col in frame.columns]].copy()


def _fetch_remote_symbols(network_cfg: NetworkRuntimeConfig) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for label, fetcher in (
        ("sse", _fetch_sse_mainboard_symbols),
        ("szse", _fetch_szse_a_symbols),
    ):
        try:
            frame = fetcher(network_cfg)
            if frame.empty:
                errors.append(f"{label}: empty")
                continue
            frames.append(frame)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    if errors:
        raise RuntimeError(f"remote symbol fetch failed; {'; '.join(errors)}")
    merged = pd.concat(frames, ignore_index=True)
    merged["code"] = merged["code"].astype(str).str.zfill(6)
    merged["name"] = merged["name"].fillna("")
    return merged.drop_duplicates("code").sort_values("code").reset_index(drop=True)


def build_symbols(project: str, db_path: Path, freq: str, target_size: int | None = None) -> tuple[Path, Path, int, str]:
    try:
        frame = _fetch_remote_symbols(NetworkRuntimeConfig.from_sources())
        frame["board"] = frame["code"].apply(_board)
        frame["is_st"] = frame["name"].apply(_is_st)
        frame = frame[(frame["board"] == "mainboard") & (~frame["is_st"])].copy()
        if target_size and target_size > 0 and len(frame) > target_size:
            frame = frame.head(target_size).copy()
        symbols_path, universe_path, count = _finalize_symbols(project, frame)
        return symbols_path, universe_path, count, "remote"
    except Exception:
        db_result = _build_symbols_from_db(project=project, db_path=db_path, freq=freq, target_size=target_size)
        if db_result is not None:
            symbols_path, universe_path, count = db_result
            return symbols_path, universe_path, count, "db"
        symbols_path, universe_path, count = _build_symbols_from_akshare(project=project, target_size=target_size)
        return symbols_path, universe_path, count, "akshare"


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the project universe.")
    parser.add_argument("--project", type=str, default="2026Q1_limit_up")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg, _ = load_config(args.project, config_path=args.config)
    target_size = cfg.get("universe_size_target")
    symbols_path, universe_path, count, source = build_symbols(
        project=args.project,
        db_path=Path(cfg["db_path"]),
        freq=str(cfg["freq"]),
        target_size=target_size,
    )
    update_run_manifest(
        args.project,
        {
            "symbols_path": str(symbols_path),
            "universe_path": str(universe_path),
            "universe_size": count,
            "symbols_source": source,
        },
    )
    print(f"[symbols] source={source} saved={symbols_path} universe={universe_path} size={count}")


if __name__ == "__main__":
    main()
