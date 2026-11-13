"""Validated, explicitly scoped ANTAQ navigation and regional reference indicators."""

import hashlib
import json
from pathlib import Path

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_water"
CONTRACTS = {"navigation_totals": (3, "million_tonnes"),
             "inland_commodities": (10, "million_tonnes"),
             "coastal_state_endpoints": (22, "thousand_TEU"),
             "grain_regions": (8, "million_tonnes")}


def load_water(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported ANTAQ snapshot schema")
    record, = metadata["files"]
    if record["path"] != "water.csv":
        raise ValueError("Unexpected ANTAQ snapshot path")
    raw = (root / "water.csv").read_bytes()
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("ANTAQ snapshot integrity mismatch")
    data = pl.read_csv(raw)
    columns = {"dataset", "category", "direction", "year", "value", "unit",
               "source_page", "source_url", "scope"}
    if set(data.columns) != columns or data.is_empty() or any(data.null_count().row(0)):
        raise ValueError("Incomplete ANTAQ snapshot")
    if set(data["dataset"]) != set(CONTRACTS):
        raise ValueError("Unexpected ANTAQ dataset coverage")
    if not data["value"].dtype.is_numeric() or not data["value"].is_finite().all():
        raise ValueError("Invalid ANTAQ values")
    if (data["value"] < 0).any() or data.select("dataset", "category", "direction", "year").is_duplicated().any():
        raise ValueError("Negative or duplicate ANTAQ indicator")
    if not data["year"].dtype.is_integer() or set(data["year"]) != {2024, 2025}:
        raise ValueError("Invalid ANTAQ reference period")
    for name, (count, unit) in CONTRACTS.items():
        subset = data.filter(pl.col("dataset") == name)
        if subset.height != count or set(subset["unit"]) != {unit}:
            raise ValueError("ANTAQ units or row coverage differ from reviewed contract")
        years = {2024, 2025} if name == "grain_regions" else {2025}
        directions = ({"origin", "destination"} if name == "coastal_state_endpoints" else
                      {"movements", "exports"} if name == "grain_regions" else {"not_applicable"})
        if set(subset["year"]) != years or set(subset["direction"]) != directions:
            raise ValueError("ANTAQ direction or reference year differs from reviewed contract")
    return data.sort("dataset", "year", "direction", "category"), metadata
