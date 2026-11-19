"""Validate historical ANP year bundles and preserve changing coverage."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import polars as pl

from freight_intelligence.ingestion.brazil_gas import (
    LEGACY_UNITS_FILE,
    LEGACY_UNITS_SHA256,
    LEGACY_UNITS_URL,
    annual_volumes,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_gas_history"


def load_gas_history(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    signature = tuple((name, (root / name).stat().st_mtime_ns, (root / name).stat().st_size)
                      for name in ("provenance.json", "monthly.csv", "annual.json", LEGACY_UNITS_FILE)
                      if (root / name).exists())
    return _cached_history(root, signature)


@lru_cache(maxsize=1)
def _cached_history(root, signature):
    # Read-only shared data avoids duplicating the detailed coverage dictionary
    # for every dashboard session. Callers filter frames without mutating metadata.
    root = Path(root)
    raw_metadata = (root / "provenance.json").read_bytes()
    if len(raw_metadata) > 8 * 1024**2:
        raise ValueError("Historical gas provenance exceeds size limit")
    metadata = json.loads(raw_metadata)
    files = metadata["files"]
    expected_files = {"monthly.csv", "annual.json"}
    if 2021 in metadata["years"]:
        expected_files.add(LEGACY_UNITS_FILE)
        expected_contract = {"url": LEGACY_UNITS_URL, "sha256": LEGACY_UNITS_SHA256,
                             "file": LEGACY_UNITS_FILE, "version": "2026-06-12", "page": 2,
                             "year": 2021, "variable": "Volume Realizado", "unit": "thousand_m3"}
        if metadata.get("legacy_unit_contract") != expected_contract:
            raise ValueError("Invalid historical gas unit contract")
        if hashlib.sha256((root / LEGACY_UNITS_FILE).read_bytes()).hexdigest() != LEGACY_UNITS_SHA256:
            raise ValueError("Historical gas unit contract integrity mismatch")
    if (metadata.get("schema_version") != 1 or len(files) != len(expected_files)
            or {r["path"] for r in files} != expected_files):
        raise ValueError("Invalid historical gas manifest")
    for record in files:
        raw = (root / record["path"]).read_bytes()
        if len(raw) > 2 * 1024**2 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Historical gas integrity mismatch")
    data = pl.read_csv(root / "monthly.csv", schema_overrides={"operator_id": pl.String})
    annuals = json.loads((root / "annual.json").read_bytes())
    if (data.is_empty() or any(data.null_count().row(0)) or data.height > 2000
            or set(data["year"]) != set(metadata["years"])
            or {a["year"] for a in annuals} != set(metadata["years"])):
        raise ValueError("Invalid historical gas coverage")
    for annual in annuals:
        year = annual["year"]
        if not 2021 <= year < 2025:
            raise ValueError("Invalid historical gas year")
        rows = data.filter(pl.col("year") == year)
        expected = annual_volumes(rows.to_dicts())
        for kind in ("receipt", "delivery"):
            if not math.isclose(expected[kind], annual[kind], rel_tol=1e-12):
                raise ValueError("Historical gas annual/monthly mismatch")
        for field in ("missing_daily_values", "negative_daily_values"):
            if expected[field] != annual[field]:
                raise ValueError("Historical gas quality counts disagree")
        sources = [s for s in metadata["sources"] if s["year"] == year]
        if len(sources) != 12 or {s["month"] for s in sources} != set(range(1, 13)):
            raise ValueError("Missing historical gas source months")
        for source in sources:
            if year == 2021 and source.get("legacy_unit_contract_sha256") != LEGACY_UNITS_SHA256:
                raise ValueError("Missing historical gas source unit contract")
            subset = rows.filter(pl.col("month") == source["month"])
            if (subset["missing_daily_values"].sum() != source["missing_daily_values"]
                    or sum(len(g["dates"]) for g in source["missing_groups"]) != source["missing_daily_values"]
                    or subset["observed_daily_values"].sum() + subset["missing_daily_values"].sum() != source["daily_values"]):
                raise ValueError("Historical gas source diagnostics disagree")
    return data, annuals, metadata


def missing_groups(metadata, point_type, operator_id=None, month=None):
    output = []
    for source in metadata["sources"]:
        if month is not None and source["month"] != month:
            continue
        groups = source.get("missing_groups")
        if groups is None:
            grouped = {}
            for cell in source.get("missing_cells", []):
                key = (cell["operator_id"], cell["point_id"], cell["source_record"])
                group = grouped.setdefault(key, {k: v for k, v in cell.items() if k != "date"})
                group.setdefault("dates", []).append(cell["date"])
            groups = list(grouped.values())
        for group in groups:
            if group["point_type"] != point_type or (
                    operator_id is not None and group["operator_id"] != operator_id):
                continue
            output.append({**group, "missing_days": len(group["dates"]),
                           "source_url": source["url"], "source_sha256": source["sha256"]})
    return output
