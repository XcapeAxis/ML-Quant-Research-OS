from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Quant MVP Dashboard", layout="wide")

root = Path(__file__).resolve().parents[1]
projects_root = root / "artifacts" / "projects"
projects = sorted([p.name for p in projects_root.glob("*") if p.is_dir()]) if projects_root.exists() else []

st.title("Quant MVP Dashboard")
project = st.selectbox("Project", options=projects or ["as_share_research_v1"])

artifact_dir = root / "artifacts" / "projects" / project
meta_dir = root / "data" / "projects" / project / "meta"

st.subheader("Summary Metrics")
metrics_path = artifact_dir / "summary_metrics.csv"
if metrics_path.exists():
    metrics = pd.read_csv(metrics_path)
    st.dataframe(metrics, use_container_width=True)
else:
    st.info(f"Missing metrics file: {metrics_path}")

st.subheader("Equity Curve")
curve_path = artifact_dir / "equity_curve.png"
if not curve_path.exists():
    curve_path = artifact_dir / "topn_1_5.png"
if curve_path.exists():
    st.image(str(curve_path))
else:
    st.info("Missing curve image: equity_curve.png or topn_1_5.png")

st.subheader("Run Manifest")
manifest_path = meta_dir / "run_manifest.json"
if manifest_path.exists():
    st.json(pd.read_json(manifest_path, typ="series").to_dict())
else:
    st.info(f"Missing manifest: {manifest_path}")
