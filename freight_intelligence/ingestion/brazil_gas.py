"""Validate ANP daily gas-point reports without mixing receipts and deliveries."""

import calendar
import csv
import hashlib
import io
import re
from collections import defaultdict
from decimal import Decimal

MAX_BYTES = 8 * 1024 * 1024
POINT_TYPES = {"Ponto de Recebimento": "receipt", "Ponto de Entrega": "delivery"}
HEADERS = [
    "Código da Instalação de Transporte", "Nome da Instalação de Transporte",
    "Nome da Instalação de Gasoduto", "Código da Instalação de Gasoduto",
    "Tipo da instalação de Gasoduto", "Nome do Município da Instalação de Gasoduto",
    "Nome da UF da Instalação de Gasoduto", "Nome do Operador da instalação de Gasoduto",
    "Código do Operador da Instalação de Gasoduto",
    "Nome do Carregador que usa a Instalação de Gasoduto",
    "Código do Carregador que usa a Instalação de Gasoduto",
    "Nome do Contrato da Instalação de Gasoduto", "Nome da Variável",
]


def parse_number(value):
    text = value.strip()
    if len(text) > 32 or not re.fullmatch(
        r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?(?:[Ee][+-]?\d{1,2})?", text
    ):
        raise ValueError("Missing or invalid ANP realized volume")
    return Decimal(text.replace(".", "").replace(",", "."))


def parse_month(raw, year, month):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Empty or oversized ANP gas report")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    header = next(reader)
    days = calendar.monthrange(year, month)[1]
    expected_dates = [f"{day:02}/{month:02}/{year}" for day in range(1, days + 1)]
    if (header[:13] != HEADERS or header[13:13 + days] != expected_dates
            or any(value.strip() for value in header[13 + days:])):
        raise ValueError("ANP gas columns or full calendar month differ from the contract")
    totals, seen, operator_names = defaultdict(Decimal), set(), {}
    missing, observed, negatives = defaultdict(int), defaultdict(int), defaultdict(int)
    source_rows, selected_rows = 0, 0
    for row in reader:
        if not row or all(not value.strip() for value in row):
            continue
        source_rows += 1
        if len(row) != len(header):
            raise ValueError("ANP gas report has malformed rows")
        if any(value.strip() for value in row[13 + days:]):
            raise ValueError("ANP gas report contains values outside calendar-day columns")
        if row[12].strip() != "Volume Realizado (mil m³)":
            continue
        point_type = POINT_TYPES.get(row[4].strip())
        if point_type is None:
            raise ValueError("Unknown ANP realized-volume point type")
        if any(not row[index].strip() for index in (0, 3, 7, 8, 10)):
            raise ValueError("ANP realized volume lacks required identifiers")
        key = tuple(row[index].strip() for index in (0, 3, 4, 8, 10, 11))
        if key in seen:
            raise ValueError("Duplicate ANP point/operator/shipper/contract volume row")
        seen.add(key)
        operator_id, operator = row[8].strip(), row[7].strip()
        if operator_id in operator_names and operator_names[operator_id] != operator:
            raise ValueError("Conflicting ANP operator identities")
        operator_names[operator_id] = operator
        group = (operator_id, point_type)
        totals[group] += Decimal(0)
        for cell in row[13:13 + days]:
            if not cell.strip():
                missing[group] += 1
                continue  # Missing remains missing, never a zero-volume observation.
            value = parse_number(cell)
            totals[group] += value
            observed[group] += 1
            negatives[group] += int(value < 0)
        selected_rows += 1
    if not selected_rows or {key[1] for key in totals} != {"receipt", "delivery"}:
        raise ValueError("ANP month lacks realized receipts or deliveries")
    rows = [{"year": year, "month": month, "operator_id": operator_id,
             "operator": operator_names[operator_id], "point_type": point_type,
             "volume_thousand_m3": float(total), "calendar_days": days,
             "observed_daily_values": observed[(operator_id, point_type)],
             "missing_daily_values": missing[(operator_id, point_type)],
             "negative_daily_values": negatives[(operator_id, point_type)]}
            for (operator_id, point_type), total in sorted(totals.items())]
    return rows, {"year": year, "month": month, "sha256": hashlib.sha256(raw).hexdigest(),
                  "bytes": len(raw), "source_rows": source_rows,
                  "realized_volume_rows": selected_rows, "daily_values": selected_rows * days,
                  "missing_daily_values": sum(missing.values()),
                  "negative_daily_values": sum(negatives.values())}


def annual_volumes(monthly):
    """Reject partial years; report gross point events, never receipts plus deliveries."""
    if not monthly:
        raise ValueError("No gas observations")
    year, = {row["year"] for row in monthly}
    if {row["month"] for row in monthly} != set(range(1, 13)):
        raise ValueError("A complete twelve-month gas year is required")
    seen, totals = set(), defaultdict(Decimal)
    for row in monthly:
        key = (row["month"], row["operator_id"], row["point_type"])
        if key in seen or row["point_type"] not in {"receipt", "delivery"}:
            raise ValueError("Duplicate or invalid monthly gas aggregation")
        seen.add(key)
        if row["calendar_days"] != calendar.monthrange(year, row["month"])[1]:
            raise ValueError("Incorrect gas observation calendar")
        value = Decimal(str(row["volume_thousand_m3"]))
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid aggregated gas volume")
        totals[row["point_type"]] += value
    for month in range(1, 13):
        if {row["point_type"] for row in monthly if row["month"] == month} != {"receipt", "delivery"}:
            raise ValueError("Missing gas point type in a calendar month")
    # Explicit conversion: source thousand m3 to million m3. No density conversion.
    return {"year": year, **{kind: float(value / 1000) for kind, value in totals.items()},
            "missing_daily_values": {
                kind: sum(row["missing_daily_values"] for row in monthly if row["point_type"] == kind)
                for kind in ("receipt", "delivery")
            },
            "negative_daily_values": sum(row["negative_daily_values"] for row in monthly)}
