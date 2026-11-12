"""Serve the dashboard and a read-only API from the same reviewed snapshot.

Launch with ``streamlit run freight_intelligence/hosted_app.py``.
No local optimization outputs, uploads or user scenarios are published.
"""

import os
from pathlib import Path

import streamlit as st
from starlette.routing import Mount

from freight_intelligence.api.app import create_app

PROJECT = Path(__file__).resolve().parents[1]


def snapshot_api(root: Path):
    """Pin every reader to the public snapshot, including optional results."""
    return create_app(
        gold_dir=root / "data/gold/faf5",
        model_dir=root / "models/faf5/annual",
        evaluation_dir=root / "artifacts/evaluation/annual",
        transport_dir=root / "artifacts/optimization/transport",
        brazil_dir=PROJECT / "deployment/brazil_modes",
    )


root = Path(os.environ.get("LOGINEXUS_DASHBOARD_DATA_ROOT", PROJECT / "deployment/preview_data"))
app = st.App(
    str(PROJECT / "dashboards/app.py"),
    routes=[Mount("/api", app=snapshot_api(root))],
)
