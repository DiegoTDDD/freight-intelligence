"""Parse ANTT SIADE reported railway movements without mixing FAF projections."""

import csv
import io
import re

import polars as pl

CATALOG_URL = (
    "https://dados.antt.gov.br/api/3/action/package_show?id=438a5184-09db-49a3-88c8-0bad418b4409"
)
SOURCE_PAGE = "https://dados.antt.gov.br/dataset/sistema-de-acompanhamento-do-desempenho-operacional-das-concessionarias-siade"
NUMBER = re.compile(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\Z")
COLUMNS = [
    "Mes_Ano",
    "Ferrovia",
    "Mercadoria_ANTT",
    "Estacao_Origem",
    "UF_Origem",
    "Estacao_Destino",
    "UF_Destino",
    "TU",
    "TKU",
]


def parse_number(value):
    value = value.strip()
    if not NUMBER.fullmatch(value):
        raise ValueError(f"Invalid ANTT numeric value: {value!r}")
    return float(value.replace(".", "").replace(",", "."))


def parse_movements(payload, expected_year):
    if not payload or len(payload) > 10 * 1024 * 1024:
        raise ValueError("ANTT input must be nonempty and at most 10 MiB")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if reader.fieldnames != COLUMNS:
        raise ValueError(f"Unexpected ANTT columns: {reader.fieldnames}")
    rows = []
    for row in reader:
        period = row["Mes_Ano"]
        if not re.fullmatch(r"(?:0[1-9]|1[0-2])/\d{4}", period):
            raise ValueError(f"Invalid ANTT period: {period}")
        month, year = map(int, period.split("/"))
        if year != expected_year or any(not row[key].strip() for key in COLUMNS[1:7]):
            raise ValueError("Year mismatch or missing ANTT dimension")
        rows.append(
            {
                "year": year,
                "month": month,
                "railway": row["Ferrovia"].strip(),
                "commodity": row["Mercadoria_ANTT"].strip(),
                "origin_station": row["Estacao_Origem"].strip(),
                "origin_state": row["UF_Origem"].strip(),
                "destination_station": row["Estacao_Destino"].strip(),
                "destination_state": row["UF_Destino"].strip(),
                "tons": parse_number(row["TU"]),
                "tonne_km": parse_number(row["TKU"]),
            }
        )
    if not rows or {row["month"] for row in rows} != set(range(1, 13)):
        raise ValueError("Only years containing all twelve reported months are accepted")
    return pl.DataFrame(rows)


def aggregate_movements(data):
    measures = [pl.col("tons").sum(), pl.col("tonne_km").sum()]
    tables = {}
    for name, dimensions in {
        "annual": ["year"],
        "monthly": ["year", "month"],
        "commodities": ["year", "commodity"],
        "corridors": ["year", "origin_state", "destination_state"],
        "railways": ["year", "railway"],
    }.items():
        tables[name] = data.group_by(dimensions).agg(measures).sort(dimensions)
    observations = (
        tables["annual"]
        .unpivot(
            index="year",
            on=["tons", "tonne_km"],
            variable_name="metric_type",
            value_name="total_value",
        )
        .select("metric_type", "year", "total_value")
        .sort(["metric_type", "year"])
    )
    return tables, observations
