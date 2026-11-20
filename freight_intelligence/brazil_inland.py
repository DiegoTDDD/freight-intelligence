"""Reviewed transport on inland waterways; never combine with port handling."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_water import DEFAULT_ROOT

CONTRACT_SHA256 = "8a75f017e12bd2369f504d4d453f6f03e021bb2133fae05343e32b177caa0140"
COMPONENTS = ("international_inland", "cabotage_inland", "inland_navigation")
SOURCE_LABELS = {"international_inland": "Longo Curso em vias interiores",
                 "cabotage_inland": "Cabotagem em vias interiores", "inland_navigation": "Navegação Interior"}
FILES = {"monthly": "inland_monthly.csv", "annual": "inland_annual.csv",
         "navigation": "inland_navigation_2025.csv", "commodities": "inland_commodities_2025.csv"}
TOLERANCE = 0.0001  # Export summation artifacts, not physical measurement accuracy.


def read_contract(root):
    raw = (Path(root) / "inland_provenance.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("Changed ANTAQ inland transport review contract")
    return json.loads(raw)


def annual_totals(monthly, metadata):
    columns = ["year", "month", "period", "total_tonnes", *COMPONENTS]
    if (monthly.columns != columns or monthly.height != 62 or any(monthly.null_count().row(0))
            or not monthly["year"].dtype.is_integer() or not monthly["month"].dtype.is_integer()
            or set(monthly["year"]) != set(range(2021, 2027))):
        raise ValueError("Invalid inland monthly history coverage")
    for name in ("total_tonnes", *COMPONENTS):
        values = monthly[name]
        if not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any():
            raise ValueError("Invalid inland transport quantity")
    for row in monthly.to_dicts():
        if row["total_tonnes"] <= 0 or abs(row["total_tonnes"] - math.fsum(row[name] for name in COMPONENTS)) > TOLERANCE:
            raise ValueError("Inland monthly navigation components do not reconcile")
    rows = []
    for year in range(2021, 2027):
        data = monthly.filter(pl.col("year") == year).sort("month")
        count = 2 if year == 2026 else 12
        if (data["month"].to_list() != list(range(1, count + 1))
                or data["period"].to_list() != [f"{year}-{month:02d}" for month in range(1, count + 1)]):
            raise ValueError("Changed inland source calendar")
        sums = {name: math.fsum(data[name]) for name in ("total_tonnes", *COMPONENTS)}
        displayed = metadata["displayed_period_totals"][str(year)]
        if abs(sums["total_tonnes"] - displayed) > 0.5:
            raise ValueError("Inland export does not reconcile to independent period headline")
        rows.append({"year": year, "months_observed": count, "full_year": count == 12, **sums,
                     "displayed_total_tonnes": displayed,
                     "export_minus_display_tonnes": sums["total_tonnes"] - displayed})
    return pl.DataFrame(rows)


def validate_details(tables):
    total = math.fsum(tables["monthly"].filter(pl.col("year") == 2025)["total_tonnes"])
    navigation, commodities = tables["navigation"], tables["commodities"]
    if (navigation.columns != ["year", "navigation", "source_label", "tonnes", "share"]
            or navigation.height != 3 or any(navigation.null_count().row(0))
            or set(navigation["year"]) != {2025} or set(navigation["navigation"]) != set(COMPONENTS)):
        raise ValueError("Invalid inland navigation reference")
    for row in navigation.to_dicts():
        if (row["source_label"] != SOURCE_LABELS[row["navigation"]]
                or not math.isfinite(row["tonnes"]) or row["tonnes"] <= 0
                or not math.isfinite(row["share"]) or not 0 <= row["share"] <= 1
                or not math.isclose(row["tonnes"] / total, row["share"], rel_tol=0, abs_tol=1e-10)
                or abs(math.fsum(tables["monthly"].filter(pl.col("year") == 2025)[row["navigation"]]) - row["tonnes"]) > TOLERANCE):
            raise ValueError("Inland annual navigation reference does not reconcile")
    if (commodities.columns != ["year", "commodity", "tonnes", "share", "quantity_status"]
            or commodities.height != 117 or set(commodities["year"]) != {2025}
            or commodities["commodity"].n_unique() != 117
            or any(commodities.select(pl.exclude("tonnes")).null_count().row(0))):
        raise ValueError("Invalid inland commodity reference")
    numeric = []
    for row in commodities.to_dicts():
        if not math.isfinite(row["share"]) or not 0 <= row["share"] <= 1:
            raise ValueError("Invalid inland source share")
        if row["quantity_status"] == "source_dash":
            if row["tonnes"] is not None:
                raise ValueError("Source dash must remain unavailable")
        elif row["quantity_status"] == "reported_numeric":
            value = row["tonnes"]
            if value is None or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid reported inland commodity tonnes")
            if not math.isclose(value / total, row["share"], rel_tol=0, abs_tol=1e-10):
                raise ValueError("Inland commodity source denominator changed")
            numeric.append(value)
        else:
            raise ValueError("Invalid inland source quantity status")
    if (len(numeric) != 109 or sum(value == 0 for value in numeric) != 46
            or abs(math.fsum(numeric) - total) > TOLERANCE
            or not math.isclose(math.fsum(commodities["share"]), 1, rel_tol=0, abs_tol=1e-10)
            or abs(math.fsum(navigation["tonnes"]) - total) > TOLERANCE):
        raise ValueError("Inland commodity coverage or reconciliation changed")


def load_inland(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    metadata = read_contract(root)
    signature = tuple((row["path"], (root / row["path"]).stat().st_mtime_ns,
                       (root / row["path"]).stat().st_size) for row in metadata["files"])
    return _load_inland(root, signature)


@lru_cache(maxsize=1)
def _load_inland(root, signature):
    metadata = read_contract(root)
    for row in metadata["files"]:
        if Path(row["path"]).name != row["path"]:
            raise ValueError("Invalid inland evidence path")
        raw = (root / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Changed inland transport evidence")
    tables = {view: pl.read_csv(root / name) for view, name in FILES.items()}
    annual = annual_totals(tables["monthly"], metadata)
    if annual.write_csv().encode() != (root / FILES["annual"]).read_bytes():
        raise ValueError("Inland monthly/annual tables differ")
    validate_details(tables)
    return tables, metadata
