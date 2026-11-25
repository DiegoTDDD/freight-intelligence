"""Serve the dashboard and a read-only API from the same reviewed snapshot.

Launch with ``streamlit run freight_intelligence/hosted_app.py``.
No local optimization outputs, uploads or user scenarios are published.
"""

import os
from pathlib import Path

import streamlit as st
from starlette.routing import Mount

from freight_intelligence.api.public_snapshot import snapshot_api

PROJECT = Path(__file__).resolve().parents[1]


root = Path(os.environ.get("LOGINEXUS_DASHBOARD_DATA_ROOT", PROJECT / "deployment/preview_data"))
app = st.App(
    str(PROJECT / "dashboards/app.py"),
    routes=[Mount("/api", app=snapshot_api(root))],
)
