"""Integrity-checked published road freight flows between immediate regions."""

import hashlib
import json
from pathlib import Path

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_road"
STATES = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"


def _load_bundle(root):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported road snapshot schema")
    records = metadata["files"]
    if len(records) != 2 or {r["path"] for r in records} != {"regional_flows.csv", "monthly.csv"}:
        raise ValueError("Unexpected road snapshot path")
    tables = {}
    for record in records:
        raw = (root / record["path"]).read_bytes()
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Road snapshot integrity mismatch")
        tables[record["path"]] = pl.read_csv(raw)
    data = tables["regional_flows.csv"]
    columns = {"year", "origin_state", "origin_region", "destination_state",
               "destination_region", "tonnes", "reported_share_percent"}
    if set(data.columns) != columns or data.height != 16 or any(data.null_count().row(0)):
        raise ValueError("Incomplete reviewed road flow table")
    if not data["year"].dtype.is_integer() or set(data["year"]) != {2025}:
        raise ValueError("Invalid road reference year")
    if not data["tonnes"].dtype.is_integer() or (data["tonnes"] <= 0).any():
        raise ValueError("Invalid road tonnes")
    for name in ("origin_state", "destination_state"):
        if data[name].dtype != pl.String or not set(data[name]).issubset(STATES.split("|")):
            raise ValueError("Invalid road state")
    for name in ("origin_region", "destination_region"):
        if data[name].dtype != pl.String or not data[name].str.strip_chars().str.len_chars().min():
            raise ValueError("Invalid immediate region")
    share = data["reported_share_percent"]
    if (not share.dtype.is_numeric() or not share.is_finite().all()
            or (share <= 0).any() or (share > 100).any()):
        raise ValueError("Invalid reported road shares")
    if data.select("origin_state", "origin_region", "destination_state", "destination_region").is_duplicated().any():
        raise ValueError("Duplicate road flow")
    monthly = tables["monthly.csv"]
    if (set(monthly.columns) != {"year", "month", "tonnes", "reported_paid_share_percent"}
            or monthly.height != 12 or any(monthly.null_count().row(0))
            or not all(dtype.is_integer() for dtype in monthly.dtypes)
            or set(monthly["year"]) != {2025} or set(monthly["month"]) != set(range(1, 13))
            or (monthly["tonnes"] <= 0).any()
            or not monthly["reported_paid_share_percent"].is_between(0, 100).all()):
        raise ValueError("Invalid monthly road series")
    reconciliation = metadata["reconciliation"]
    total = monthly["tonnes"].sum()
    if (total != reconciliation["annual_tonnes"]
            or reconciliation["status"] != "annual_total_reconstructed_from_monthly_chart"
            or abs(total / 1e9 - reconciliation["summary_rounded_billion_tonnes"]) >= 0.05):
        raise ValueError("Road annual total does not reconcile with monthly series and rounded summary")
    return data.sort("tonnes", descending=True), monthly.sort("month"), metadata


def load_road(root=DEFAULT_ROOT):
    data, _, metadata = _load_bundle(root)
    return data, metadata


def load_road_monthly(root=DEFAULT_ROOT):
    _, monthly, metadata = _load_bundle(root)
    return monthly, metadata
