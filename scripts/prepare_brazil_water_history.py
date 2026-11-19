"""Rebuild reviewed monthly ANTAQ history from pinned original XLSX exports."""

import hashlib
import math
from pathlib import Path

import openpyxl
import polars as pl

from freight_intelligence.brazil_water_history import (
    DEFAULT_ROOT,
    MONTHS,
    annual_totals,
    read_contract,
)


def parse_workbook(path, year):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != ["Sheet1"]:
            raise ValueError("Unexpected ANTAQ monthly workbook sheets")
        rows = list(workbook.active.values)
    finally:
        workbook.close()
    if not rows or rows[0] != ("Mês", "Ano", "Peso Carga Bruta"):
        raise ValueError("Changed ANTAQ monthly export headers")
    count = 2 if year == 2026 else 12
    if len(rows) != count + 1:
        raise ValueError("Changed ANTAQ monthly export calendar")
    result = []
    for month, (label, source_year, value) in enumerate(rows[1:], 1):
        if (label != MONTHS[month - 1] or source_year != str(year)
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("Invalid ANTAQ exported month, year or numeric tonnes")
        result.append({"year": year, "month": month, "period": f"{year}-{month:02d}", "tonnes": value})
    return pl.DataFrame(result)


def prepare(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = read_contract(root)
    for row in metadata["files"]:
        if row["path"] in {"history_monthly.csv", "history_annual.csv"}:
            continue
        raw = (root / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Changed ANTAQ original monthly export evidence")
    monthly = pl.concat([parse_workbook(root / f"history_{year}.xlsx", year) for year in range(2021, 2027)])
    tables = {"monthly": monthly, "annual": annual_totals(monthly, metadata)}
    outputs = {}
    for name, data in tables.items():
        raw = data.write_csv().encode()
        expected = next(row for row in metadata["files"] if row["path"] == f"history_{name}.csv")
        if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise ValueError("Rebuilt ANTAQ history differs from reviewed table")
        outputs[f"history_{name}.csv"] = raw
    for name, raw in outputs.items():
        (root / name).write_bytes(raw)
    return tables


if __name__ == "__main__":
    print(f"Prepared {prepare()['monthly'].height} reviewed ANTAQ monthly observations")
