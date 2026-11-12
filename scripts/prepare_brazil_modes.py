"""Rebuild reviewed cross-mode indicators, retaining published chart precision.

Values were transcribed and checked against the cited official PDF charts.
This is a reproducible curated indicator snapshot, not an automated source feed.
Optionally verify the exact reviewed source with --source-pdf PATH.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "https://ontl.infrasa.gov.br/wp-content/uploads/2025/10/"
    "Diagnostico-logistico-2010-2024.pdf"
)
SOURCE_SHA256 = "5534dc1dd04112611514c67f2d5abf35f8bce4e49f5e66f91f86503b05c73f5b"
SERIES = [
    ("road", "registered_trucks", "million_vehicles", 40,
     "Registered truck fleet (Senatran); stock, not transported cargo or active capacity",
     [2.6, 2.7, 2.9, 3.0, 3.2, 3.2, 3.3, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9, 4.0, 4.1]),
    ("water", "port_throughput", "million_tonnes", 78,
     "Brazilian port cargo handling (ANTAQ); includes maritime/inland port activity, not unique shipments",
     [838, 887, 904, 929, 969, 1008, 1003, 1088, 1123, 1106, 1156, 1209, 1221, 1305, 1322]),
    ("air", "domestic_paid_cargo", "million_kg", 110,
     "Paid domestic air cargo (ANAC); excludes unpaid cargo",
     [386.1, 412.7, 387.8, 396.0, 386.6, 343.6, 325.1, 350.9, 396.8, 389.0,
      276.9, 333.6, 363.2, 377.3, 423.0]),
    ("air", "international_paid_cargo", "million_kg", 110,
     "Paid international air cargo linked to Brazil (ANAC); not domestic-only cargo",
     [637.5, 723.3, 747.9, 800.0, 790.7, 750.3, 716.0, 802.1, 906.6, 808.8,
      711.2, 961.5, 984.4, 922.6, 1012.8]),
    ("pipeline", "natural_gas_daily_movement", "million_m3_per_day", 120,
     "Annual average daily gas movement; MME attribution in chart 69; not annual tonnes",
     [62.8, 65.9, 70.4, 77.3, 87.4, 96.2, 103.6, 109.2, 111.9, 122.4,
      127.4, 133.7, 137.9, 149.8, 153.1]),
    ("pipeline", "transpetro_oil_pipeline_movement", "million_m3_at_20C", 123,
     "Transpetro-reported oil/product pipeline volume; excludes other operators and mineral pipelines",
     [71.9, 73.7, 72.2, 76.7, 74.0, 66.9, 67.4, 63.0, 61.2, 58.1,
      56.4, 64.9, 70.6, 80.1, 79.3]),
]


def prepare(output, source_pdf=None):
    if (source_pdf is not None
            and hashlib.sha256(Path(source_pdf).read_bytes()).hexdigest() != SOURCE_SHA256):
        raise ValueError("Source PDF differs from the reviewed edition; review before updating")
    rows = []
    for mode, indicator, unit, page, scope, values in SERIES:
        assert len(values) == 15
        rows.extend({
            "mode": mode, "indicator": indicator, "year": year, "value": float(value),
            "unit": unit, "scope": scope, "source_url": SOURCE,
            "source_page": page, "status": "reported_rounded_chart_value",
        } for year, value in zip(range(2010, 2025), values, strict=True))
    rail_path = ROOT / "deployment/brazil_data/annual.parquet"
    rail = pl.read_parquet(rail_path)
    rail_source = "https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409"
    for indicator, column, unit in (("rail_net_tonnes", "tons", "tonnes"),
                                    ("rail_transport_work", "tonne_km", "tonne_km")):
        rows.extend({
            "mode": "rail", "indicator": indicator, "year": row["year"],
            "value": float(row[column]), "unit": unit,
            "scope": "Federal railway concessions (ANTT/SIADE); reported movements may repeat cargo",
            "source_url": rail_source, "source_page": 0, "status": "reported_administrative",
        } for row in rail.to_dicts())
    rows.sort(key=lambda row: (row["mode"], row["indicator"], row["year"]))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = buffer.getvalue().encode()
    metadata = {
        "schema_version": 1, "country": "Brazil", "prepared_on": "2026-11-12",
        "method": "Reviewed transcription of published chart labels plus verified ANTT rail snapshot",
        "interpretation": "Separate modal indicators; not a comparable modal split or complete shipment census",
        "sources": [{"url": SOURCE, "sha256": SOURCE_SHA256,
                     "pages": [40, 78, 110, 120, 123]},
                    {"url": rail_source, "snapshot_sha256": hashlib.sha256(
                        rail_path.read_bytes()).hexdigest()}],
        "quality_notes": [
            "Do not sum unlike units or calculate freight modal shares from these indicators.",
            "Road coverage is registered fleet history, not a road cargo volume series.",
            ("ANTT TRC 2025 cites approximately 1.4 billion tonnes on PDF page 61 and "
            "1.165 billion on page 64 (printed pages 53 and 56); no road tonnage total "
            "is promoted here until that scope discrepancy is reconciled."),
            ("Pipeline gas source attribution differs between narrative (ANP) and chart (MME); "
            "chart attribution is retained. Oil pipelines cover Transpetro, not all operators."),
            "Chart values retain source rounding; forecasts are not included.",
        ],
        "files": [{"path": "indicators.csv", "sha256": hashlib.sha256(data).hexdigest(),
                   "bytes": len(data)}],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "indicators.csv").write_bytes(data)
    (output / "provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_modes")
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source_pdf)} explicitly scoped modal indicators")
