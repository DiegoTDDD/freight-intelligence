"""Reviewed ANTAQ monthly numeric exports, with explicit partial-year coverage."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_water import DEFAULT_ROOT

CONTRACT_SHA256 = "b8e76e3c9bad8d5c2d31cb21bb0e961a658fa7d78e27b8452070439db4515345"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def read_contract(root):
    raw = (Path(root) / "history_provenance.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("Changed ANTAQ monthly history review contract")
    return json.loads(raw)


def annual_totals(monthly, metadata):
    if (monthly.columns != ["year", "month", "period", "tonnes"] or monthly.height != 62
            or any(monthly.null_count().row(0)) or not monthly["tonnes"].dtype.is_numeric()
            or not monthly["tonnes"].is_finite().all() or (monthly["tonnes"] <= 0).any()
            or not monthly["year"].dtype.is_integer() or not monthly["month"].dtype.is_integer()
            or set(monthly["year"]) != set(range(2021, 2027))):
        raise ValueError("Invalid ANTAQ monthly history values or coverage")
    rows = []
    for year in range(2021, 2027):
        data = monthly.filter(pl.col("year") == year).sort("month")
        count = 2 if year == 2026 else 12
        if (data["month"].to_list() != list(range(1, count + 1))
                or data["period"].to_list() != [f"{year}-{month:02d}" for month in range(1, count + 1)]):
            raise ValueError("Missing, duplicated or changed ANTAQ source months")
        total = math.fsum(data["tonnes"])
        displayed = metadata["annual_display_tonnes"][str(year)]
        if abs(total - displayed) > 0.5:
            raise ValueError("ANTAQ exported monthly values do not reconcile with displayed total")
        rows.append({"year": year, "months_observed": count, "full_year": count == 12,
                     "tonnes": total, "displayed_total_tonnes": displayed,
                     "export_minus_display_tonnes": total - displayed})
    return pl.DataFrame(rows)


def load_water_history(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    metadata = read_contract(root)
    signature = tuple((row["path"], (root / row["path"]).stat().st_mtime_ns,
                       (root / row["path"]).stat().st_size) for row in metadata["files"])
    return _load_history(root, signature)


@lru_cache(maxsize=1)
def _load_history(root, signature):
    metadata = read_contract(root)
    for row in metadata["files"]:
        if Path(row["path"]).name != row["path"]:
            raise ValueError("Invalid ANTAQ monthly evidence path")
        raw = (root / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Changed ANTAQ monthly history evidence")
    monthly = pl.read_csv(root / "history_monthly.csv")
    annual = annual_totals(monthly, metadata)
    if annual.write_csv().encode() != (root / "history_annual.csv").read_bytes():
        raise ValueError("ANTAQ monthly/annual history mismatch")
    return {"monthly": monthly, "annual": annual}, metadata
