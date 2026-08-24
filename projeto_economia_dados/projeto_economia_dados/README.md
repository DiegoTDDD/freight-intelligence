# Freight Intelligence - Data Platform & Economics Pipeline

A production-grade, containerized end-to-end ELT data platform designed to ingest, transform, store, and visualize macroeconomic indicators and Bitcoin metrics.

## Architecture Overview
- **Storage Layer:** PostgreSQL 15 running in a dedicated Docker container (`db_gold`).
- **Presentation Layer:** Reactive web dashboard built with Streamlit and Plotly running inside Docker (`app_stream_gold`).
- **Orchestration:** Python-based master orchestrator for automated data pipelines.
- **CI/CD:** Automated testing pipeline via GitHub Actions.

## Quickstart (Using Makefile)

1. **Start the Infrastructure (PostgreSQL + Streamlit):**
   ```bash
   make up
   ```

2. **Initialize Database Schemas:**
   ```python
   python init_db.py
   ```

3. **Run Health Monitor:**
   ```bash
   make monitor
   ```

4. **Run Unit Tests:**
   ```bash
   make test
   ```

5. **Stop Infrastructure:**
   ```bash
   make down
   ```

## Access Dashboard
Open your browser at: `http://localhost:8501`
