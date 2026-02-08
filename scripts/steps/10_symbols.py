from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quant_mvp.config import load_config
from quant_mvp.manifest import update_run_manifest
from quant_mvp.project import resolve_project_paths
from quant_mvp.universe import save_universe_codes


def _board(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith(("688", "689")):
        return "star"
    if code.startswith("3"):
        return "chinext"
    if code.startswith(("8", "4")):
        return "bse"
    if code.startswith(("0", "6")):
        return "mainboard"
    return "unknown"


def _is_st(name: str) -> bool:
    upper = str(name or "").upper()
    return "ST" in upper or "退" in upper


def _valid_mainboard(code: str) -> bool:
    code = str(code).zfill(6)
    if not code.startswith(("0", "6")):
        return False
    if code.startswith(("688", "689", "300", "301", "8", "4")):
        return False
    return True


def build_symbols(project: str, target_size: int | None = None) -> tuple[Path, Path, int]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required to build symbols.") from exc

    df = ak.stock_info_a_code_name()
    df.columns = [str(col).lower() for col in df.columns]

    rename_map = {}
    for col in df.columns:
        if col in {"代码", "code"}:
            rename_map[col] = "code"
        if col in {"名称", "name"}:
            rename_map[col] = "name"
    df = df.rename(columns=rename_map)

    if "code" not in df.columns:
        candidates = [c for c in df.columns if "code" in c]
        if not candidates:
            raise RuntimeError(f"Cannot find code column in {df.columns.tolist()}")
        df = df.rename(columns={candidates[0]: "code"})
    if "name" not in df.columns:
        df["name"] = ""

    df["code"] = df["code"].astype(str).str.zfill(6)
    df["name"] = df["name"].fillna("")
    df["board"] = df["code"].apply(_board)
    df["is_st"] = df["name"].apply(_is_st)

    df = df[df["code"].apply(_valid_mainboard)]
    df = df[(df["board"] == "mainboard") & (~df["is_st"])]
    df = df.drop_duplicates("code").sort_values("code").reset_index(drop=True)
    if target_size and target_size > 0 and len(df) > target_size:
        df = df.head(target_size).copy()

    meta_dir = ROOT / "data" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    symbols_path = meta_dir / "symbols.csv"
    df[["code", "name", "is_st", "board"]].to_csv(symbols_path, index=False, encoding="utf-8-sig")

    universe_path = save_universe_codes(project=project, codes=df["code"].tolist())
    return symbols_path, universe_path, int(df.shape[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build universe symbols and freeze project universe.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    _ = parser.parse_args()
    args = _

    cfg, _ = load_config(args.project, config_path=args.config)
    resolve_project_paths(args.project).ensure_dirs()
    target_size = cfg.get("universe_size_target")
    symbols_path, universe_path, count = build_symbols(project=args.project, target_size=target_size)
    update_run_manifest(
        args.project,
        {
            "symbols_path": str(symbols_path),
            "universe_path": str(universe_path),
            "universe_size": count,
        },
    )
    print(f"[symbols] saved={symbols_path} universe={universe_path} size={count}")


if __name__ == "__main__":
    main()
