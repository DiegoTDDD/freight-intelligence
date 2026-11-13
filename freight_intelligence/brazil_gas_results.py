"""Read only validated, hash-checked ANP gas-point aggregates."""

import hashlib
import json
import math
from pathlib import Path

import polars as pl

from freight_intelligence.ingestion.brazil_gas import annual_volumes

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_gas"


def load_gas(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    if metadata.get("schema_version") != 1 or metadata.get("year") != 2025:
        raise ValueError("Unsupported gas snapshot")
    files = metadata["files"]
    if {record["path"] for record in files} != {"monthly.csv", "annual.json"} or len(files) != 2:
        raise ValueError("Unexpected gas snapshot files")
    for record in files:
        raw = (root / record["path"]).read_bytes()
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Gas snapshot integrity mismatch")
    monthly = pl.read_csv(root / "monthly.csv")
    if monthly.is_empty() or any(monthly.null_count().row(0)):
        raise ValueError("Missing gas aggregate fields")
    counts = ["observed_daily_values", "missing_daily_values", "negative_daily_values"]
    for name in counts:
        if not monthly[name].dtype.is_integer() or (monthly[name] < 0).any():
            raise ValueError("Invalid gas coverage counts")
    if (monthly["negative_daily_values"] > monthly["observed_daily_values"]).any():
        raise ValueError("Negative-volume count exceeds observed values")
    if set(monthly["operator"]) != set(metadata["operators"]):
        raise ValueError("Gas operator coverage differs from provenance")
    if not monthly["volume_thousand_m3"].is_finite().all():
        raise ValueError("Nonfinite gas volume")
    annual = json.loads((root / "annual.json").read_bytes())
    expected = annual_volumes(monthly.to_dicts())
    if set(annual) != set(expected):
        raise ValueError("Invalid gas annual schema")
    for kind in ("receipt", "delivery"):
        if not math.isclose(annual[kind], expected[kind], rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("Gas annual and monthly results disagree")
    for field in ("year", "missing_daily_values", "negative_daily_values"):
        if annual[field] != expected[field]:
            raise ValueError("Gas annual coverage disagrees with monthly data")
    sources = metadata["sources"]
    if len(sources) != 12 or {item["month"] for item in sources} != set(range(1, 13)):
        raise ValueError("Incomplete gas source provenance")
    for source in sources:
        rows = monthly.filter(pl.col("month") == source["month"])
        for field in ("missing_daily_values", "negative_daily_values"):
            if rows[field].sum() != source[field]:
                raise ValueError("Gas source coverage counts disagree")
        if (rows["observed_daily_values"].sum() + rows["missing_daily_values"].sum()
                != source["daily_values"]):
            raise ValueError("Gas source observation count disagrees")
    return monthly, annual, metadata
