"""Rebuild reviewed inland-waterway transport exports without a bulk pipeline."""

import hashlib
import math
from pathlib import Path

import openpyxl
import polars as pl

from freight_intelligence.brazil_inland import (
    COMPONENTS,
    DEFAULT_ROOT,
    FILES,
    SOURCE_LABELS,
    annual_totals,
    read_contract,
    validate_details,
)
from freight_intelligence.brazil_water_history import MONTHS


def workbook_rows(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != ["Sheet1"]:
            raise ValueError("Unexpected inland source sheets")
        return list(workbook.active.values)
    finally:
        workbook.close()


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid inland numeric export value")
    return float(value)


def parse_history(path, year):
    rows = workbook_rows(path)
    if rows[0] != ("Mês", "Total", *(SOURCE_LABELS[name] for name in COMPONENTS)):
        raise ValueError("Changed inland monthly export headers")
    count = 2 if year == 2026 else 12
    if len(rows) != count + 1:
        raise ValueError("Changed inland monthly source calendar")
    result = []
    for month, row in enumerate(rows[1:], 1):
        if row[0] != MONTHS[month - 1]:
            raise ValueError("Changed inland month labels or order")
        result.append({"year": year, "month": month, "period": f"{year}-{month:02d}",
                       **dict(zip(("total_tonnes", *COMPONENTS), map(numeric, row[1:]), strict=True))})
    return pl.DataFrame(result)


def parse_details(navigation_path, commodity_path):
    navigation, commodities = workbook_rows(navigation_path), workbook_rows(commodity_path)
    suffix = ("Quantidade Transportada", "Distribuição Percentual", "Crescimento/Redução")
    if (navigation[0] != ("Tipo de Navegação", *suffix) or len(navigation) != 4
            or commodities[0] != ("Nomenclatura Simplificada Mercadoria", *suffix) or len(commodities) != 118):
        raise ValueError("Changed inland detail export schema")
    labels = {label: key for key, label in SOURCE_LABELS.items()}
    nav_rows = []
    for label, tonnes, share, change in navigation[1:]:
        if label not in labels or change != "-":
            raise ValueError("Unexpected inland navigation label or reference period")
        nav_rows.append({"year": 2025, "navigation": labels[label], "source_label": label,
                         "tonnes": numeric(tonnes), "share": numeric(share)})
    cargo_rows = []
    for label, tonnes, share, change in commodities[1:]:
        if not isinstance(label, str) or not label or change != "-":
            raise ValueError("Invalid inland commodity label or source period")
        cargo_rows.append({"year": 2025, "commodity": label,
                           "tonnes": None if tonnes == "-" else numeric(tonnes),
                           "share": numeric(share),
                           "quantity_status": "source_dash" if tonnes == "-" else "reported_numeric"})
    return {"navigation": pl.DataFrame(nav_rows).sort("navigation"),
            "commodities": pl.DataFrame(cargo_rows).sort("commodity")}


def prepare(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = read_contract(root)
    for row in metadata["files"]:
        if row["path"] in FILES.values():
            continue
        raw = (root / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Changed inland original export evidence")
    monthly = pl.concat([parse_history(root / f"inland_history_{year}.xlsx", year) for year in range(2021, 2027)])
    tables = {"monthly": monthly, "annual": annual_totals(monthly, metadata),
              **parse_details(root / "inland_navigation_2025.xlsx", root / "inland_commodities_2025.xlsx")}
    validate_details(tables)
    outputs = {}
    for view, name in FILES.items():
        raw = tables[view].write_csv().encode()
        expected = next(row for row in metadata["files"] if row["path"] == name)
        if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise ValueError("Rebuilt inland table differs from reviewed export")
        outputs[name] = raw
    for name, raw in outputs.items():
        (root / name).write_bytes(raw)
    return tables


if __name__ == "__main__":
    print(f"Prepared {prepare()['monthly'].height} inland transport months")
