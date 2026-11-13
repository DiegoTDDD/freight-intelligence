"""Integrity-checked published road freight flows between immediate regions."""

import hashlib
import json
from pathlib import Path

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_road"
STATES = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"


def load_road(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported road snapshot schema")
    record, = metadata["files"]
    if record["path"] != "regional_flows.csv":
        raise ValueError("Unexpected road snapshot path")
    raw = (root / record["path"]).read_bytes()
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Road snapshot integrity mismatch")
    data = pl.read_csv(raw)
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
    return data.sort("tonnes", descending=True), metadata
