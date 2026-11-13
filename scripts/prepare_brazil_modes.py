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
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_water import load_water

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "https://ontl.infrasa.gov.br/wp-content/uploads/2025/10/"
    "Diagnostico-logistico-2010-2024.pdf"
)
SOURCE_SHA256 = "5534dc1dd04112611514c67f2d5abf35f8bce4e49f5e66f91f86503b05c73f5b"
ROAD_SOURCE = "https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/anuario_trc_2025_antt.pdf"
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
    ("pipeline", "transpetro_oil_pipeline_movement", "million_m3_at_20C", 123,
     "Transpetro-reported oil/product pipeline volume; excludes other operators and mineral pipelines",
     [71.9, 73.7, 72.2, 76.7, 74.0, 66.9, 67.4, 63.0, 61.2, 58.1,
      56.4, 64.9, 70.6, 80.1, 79.3]),
]


def prepare(output, source_pdf=None, gas_dir=None):
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
    for indicator, value, unit, status in (
        ("mdfe_recorded_trips", 80.4, "million_trips", "reported_rounded_administrative"),
        ("mdfe_transport_work", 749.4, "billion_tonne_km", "reported_derived_transport_work"),
    ):
        rows.append({
            "mode": "road", "indicator": indicator, "year": 2025, "value": value,
            "unit": unit, "scope": (
                "ANTT MDF-e interstate/intermunicipal cargo operations; excludes within-city trips; "
                "transport work uses source distance estimation, not verified truck GPS tracks"
            ), "source_url": ROAD_SOURCE, "source_page": 61, "status": status,
        })
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
    _, gas, gas_metadata = load_gas(gas_dir) if gas_dir is not None else load_gas()
    operator_count = len(gas_metadata["operators"])
    operator_label = "five" if operator_count == 5 else str(operator_count)
    missing_gas_cells = sum(gas["missing_daily_values"].values())
    for kind in ("receipt", "delivery"):
        rows.append({
            "mode": "pipeline", "indicator": f"anp_gas_{kind}_observed_subtotal",
            "year": 2025, "value": gas[kind], "unit": "million_m3",
            "scope": (
                f"ANP 2025 realized {kind}-point observed subtotal across {operator_label} reported operators; "
                f"{gas['missing_daily_values'][kind]} missing daily cells; inter-operator transfers "
                "may repeat gas. Not production, unique national supply or receipt-plus-delivery total"
            ), "source_url": gas_metadata["source"], "source_page": 0,
            "status": ("reported_partial_observed_subtotal"
                       if gas["missing_daily_values"][kind] else "reported_point_movement_subtotal"),
        })
    rows.sort(key=lambda row: (row["mode"], row["indicator"], row["year"]))
    water, water_metadata = load_water()
    water_ids = {"Port throughput": "antaq_2025_port_throughput",
                 "Coastal cabotage": "coastal_cabotage_volume",
                 "Inland navigation": "inland_navigation_volume"}
    for row in water.filter(pl.col("dataset") == "navigation_totals").to_dicts():
        rows.append({"mode": "water", "indicator": water_ids[row["category"]],
                     "year": row["year"], "value": row["value"], "unit": row["unit"],
                     "scope": row["scope"], "source_url": row["source_url"],
                     "source_page": row["source_page"], "status": "reported_rounded_reference"})
    rows.sort(key=lambda row: (row["mode"], row["indicator"], row["year"]))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = buffer.getvalue().encode()
    metadata = {
        "schema_version": 1, "country": "Brazil", "prepared_on": datetime.now(UTC).date().isoformat(),
        "method": "Reviewed transcription of published chart labels plus verified ANTT rail snapshot",
        "interpretation": "Separate modal indicators; not a comparable modal split or complete shipment census",
        "sources": [*water_metadata["sources"], {"url": SOURCE, "sha256": SOURCE_SHA256,
                     "pages": [40, 78, 110, 123]},
                    {"url": gas_metadata["source"], "files": gas_metadata["sources"]},
                    {"url": ROAD_SOURCE, "pages": [61], "edition": "Anuario TRC 2025 v1.1",
                     "verification": "Official PDF page reviewed; raw download returned HTTP 403; "
                     "no upstream file hash is claimed"},
                    {"url": rail_source, "snapshot_sha256": hashlib.sha256(
                        rail_path.read_bytes()).hexdigest()}],
        "quality_notes": [
            "Do not sum unlike units or calculate freight modal shares from these indicators.",
            ("Road coverage includes fleet history and 2025 MDF-e trips/derived transport work; "
            "within-city trips and national cargo tonnage are not covered."),
            ("ANTT TRC 2025 cites approximately 1.4 billion tonnes on PDF page 61 and "
            "1.165 billion on page 64 (printed pages 53 and 56); no road tonnage total "
            "is promoted here until that scope discrepancy is reconciled."),
            ("The former ONTL gas movement series was excluded: its 153.1 million m3/day value "
             "is identified as production in EPE BEN 2025, page 16. ANP point movements replace it; "
             f"{missing_gas_cells} missing daily cells and signed source values remain disclosed. Oil pipelines "
             "cover Transpetro, not all operators."),
            "Chart values retain source rounding; forecasts are not included.",
        ],
        "excluded_series": [{"indicator": "natural_gas_daily_movement", "years": "2010-2024",
                             "reason": "Unresolved production-versus-transport classification",
                             "verification_source": "https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-885/topico-771/Relat%C3%B3rio%20Final_BEN%202025.pdf",
                             "verification_page": 16}],
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
    parser.add_argument("--gas-dir", type=Path, help="Validated candidate gas snapshot")
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source_pdf, args.gas_dir)} explicitly scoped modal indicators")
