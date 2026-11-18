"""Aggregate the official ANAC statistical CSV without shipping raw airline records.

Keep paid cargo, free cargo and mail separate. Airport pairs describe reported
stages, not unique end-to-end consignments or routes available for booking.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from freight_intelligence.ml.historical_evaluation import historical_report

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ("https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/"
          "Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/Dados_Estatisticos.csv")
DICTIONARY = ("https://www.anac.gov.br/acesso-a-informacao/dados-abertos/areas-de-atuacao/"
              "voos-e-operacoes-aereas/dados-estatisticos-do-transporte-aereo/"
              "48-dados-estatisticos-do-transporte-aereo")
FIELDS = {"CARGA_PAGA_KG": "paid_cargo_kg", "CARGA_GRATIS_KG": "free_cargo_kg",
          "CORREIO_KG": "mail_kg"}
MEASURES = [*FIELDS.values(), "source_rows", *[f"missing_{v}" for v in FIELDS.values()]]


def aggregate(source, end_year=2025, pair_start_year=2024):
    source = Path(source)
    if not 0 < source.stat().st_size <= 450 * 1024**2:
        raise ValueError("Empty or oversized ANAC source")
    monthly, pairs = defaultdict(lambda: [0] * 7), defaultdict(lambda: [0] * 7)
    counts = defaultdict(int)
    airports = {}
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=";")
        updated = next(reader)
        header = next(row for row in reader if row)
        required = {"ANO", "MES", "NATUREZA", "GRUPO_DE_VOO", *FIELDS}
        for side in ("ORIGEM", "DESTINO"):
            required.update(f"AEROPORTO_DE_{side}_{field}" for field in ("SIGLA", "NOME", "PAIS"))
        if not required.issubset(header) or len(set(header)) != len(header):
            raise ValueError("ANAC source columns changed")
        for values in reader:
            if not values:
                continue
            counts["raw_rows"] += 1
            if len(values) != len(header):
                raise ValueError("Malformed ANAC record")
            row = dict(zip(header, values, strict=True))
            year, month = int(row["ANO"]), int(row["MES"])
            if not 2000 <= year <= 2100 or not 1 <= month <= 12:
                raise ValueError("Invalid ANAC reference period")
            if year > end_year:
                counts["excluded_future_or_partial_year_rows"] += 1
                continue
            if "BRASIL" not in (row["AEROPORTO_DE_ORIGEM_PAIS"], row["AEROPORTO_DE_DESTINO_PAIS"]):
                counts["excluded_no_brazil_endpoint_rows"] += 1
                continue
            nature = {"DOMÉSTICA": "domestic", "DOMESTICA": "domestic",
                      "DOMÉSTICO": "domestic", "DOMESTICO": "domestic",
                      "INTERNACIONAL": "international"}.get(row["NATUREZA"])
            if nature is None:
                raise ValueError(f"Unknown ANAC flight nature: {row['NATUREZA']}")
            metrics = []
            for field in FIELDS:
                value = row[field].strip()
                if not value:
                    metrics.append(None)
                    continue
                number = float(value.replace(",", "."))
                if not math.isfinite(number) or number < 0 or not number.is_integer():
                    raise ValueError("ANAC cargo values must be nonnegative integer kilograms")
                metrics.append(int(number))
            # All groups are retained; do not silently select only scheduled flights.
            counts["selected_rows"] += 1
            key = (year, month, nature)
            targets = [monthly[key]]
            origin, destination = row["AEROPORTO_DE_ORIGEM_SIGLA"], row["AEROPORTO_DE_DESTINO_SIGLA"]
            if year >= pair_start_year:
                if origin and destination:
                    targets.append(pairs[(*key, origin, destination)])
                else:
                    counts["recent_rows_missing_airport_code"] += 1
            for side, code in (("ORIGEM", origin), ("DESTINO", destination)):
                if code:
                    airports[code] = {"airport": code, "name": row[f"AEROPORTO_DE_{side}_NOME"],
                                      "country": row[f"AEROPORTO_DE_{side}_PAIS"]}
            for target in targets:
                target[3] += 1
                for index, value in enumerate(metrics):
                    if value is None:
                        target[4 + index] += 1
                    else:
                        target[index] += value
    if not monthly or not pairs:
        raise ValueError("No ANAC observations in requested scope")
    monthly_frame = pl.DataFrame([(*key, *values) for key, values in sorted(monthly.items())],
                                schema=["year", "month", "nature", *MEASURES], orient="row")
    pair_frame = pl.DataFrame([(*key, *values) for key, values in sorted(pairs.items())],
                             schema=["year", "month", "nature", "origin", "destination", *MEASURES],
                             orient="row")
    annual = monthly_frame.group_by("year", "nature").agg(
        *[pl.col(field).sum() for field in MEASURES], pl.col("month").n_unique().alias("reported_months")
    ).sort("year", "nature")
    if not annual["reported_months"].eq(12).all():
        raise ValueError("Incomplete annual ANAC month coverage; review before publishing")
    return monthly_frame, pair_frame, annual, pl.DataFrame(list(airports.values())).sort("airport"), {
        "source_update_line": updated, "counts": dict(counts), "end_year": end_year,
        "pair_start_year": pair_start_year}


def prepare(source, output, end_year=2025, pair_start_year=2024, retrieved_at=None):
    source, output = Path(source), Path(output)
    monthly, pairs, annual, airports, details = aggregate(source, end_year, pair_start_year)
    output.mkdir(parents=True, exist_ok=True)
    files = []
    for name, data in (("monthly", monthly), ("pairs", pairs), ("annual", annual), ("airports", airports)):
        path = output / f"{name}.parquet"
        data.write_parquet(path)
        raw = path.read_bytes()
        files.append({"path": path.name, "rows": data.height, "bytes": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest()})
    history = annual.filter(pl.col("year") >= 2010).select(
        pl.concat_str("nature", pl.lit("_paid_observed_subtotal")).alias("metric_type"),
        "year", pl.col("paid_cargo_kg").alias("total_value"))
    manifest = {"dataset_id": "anac_paid_stage_subtotals_2010_2025", "source": SOURCE,
                "retrieved_at": retrieved_at or datetime.now(UTC).date().isoformat(), "record_kind": "historical_observations",
                "scope": "Observed paid-cargo kilogram subtotals on Brazil-linked ANAC stages; missing fields excluded and counted; not unique consignments or a complete census",
                "units": {name: "kg" for name in history["metric_type"].unique()}}
    report = historical_report(history.write_csv().encode(), json.dumps(manifest).encode(),
                               min_train_points=8, test_points=3, forecast_years=3)
    (output / "forecast.zip").write_bytes(report)
    files.append({"path": "forecast.zip", "bytes": len(report),
                  "sha256": hashlib.sha256(report).hexdigest()})
    with source.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    metadata = {"schema_version": 1, "source": SOURCE, "dictionary": DICTIONARY,
                "source_sha256": checksum, **details,
                "interpretation": "ANAC reported airport-pair stage movements linked to Brazil; paid cargo, free cargo and mail kept separate. Stages can repeat a consignment; not unique end-to-end shipments or booking availability.",
                "quality_notes": ["Source can revise historical records; this edition is pinned by SHA-256.",
                                  "Foreign-to-foreign records and incomplete current/future years are excluded.",
                                  "All reported flight groups are retained. Nature follows the source classification.",
                                  "Missing cargo fields are excluded from sums and counted, never silently filled with zero.",
                                  "Airport-pair detail covers the two most recent complete years; annual/monthly aggregates retain older history.",
                                  "Airport totals by origin and destination overlap; do not add them as national freight."],
                "files": files}
    (output / "provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    return {"monthly": monthly.height, "pairs": pairs.height, "annual": annual.height}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_air")
    parser.add_argument("--retrieved-at", help="Actual retrieval date for an archived source (YYYY-MM-DD)")
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, retrieved_at=args.retrieved_at)))
