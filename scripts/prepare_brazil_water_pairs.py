"""Prepare reviewed regional cabotage shares from the original ANTAQ Qlik export."""

import argparse
import hashlib
import json
from pathlib import Path

import openpyxl
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "cabotage_region_pairs_2025.xlsx"
SOURCE_HASH = "183b4b2a555b0e69fb08553416be9adc31022be9e11d237c3ab6d848ce7a6ab1"
CONTEXT_NAME = "cabotage_region_pairs_2025_context.jpg"
CONTEXT_HASH = "6022792386604dc798f78802d083c86f07cc92fe7b5636c398f1e150f5888a4b"
SOURCE = ("https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808"
          "&sheet=ecb07b54-35b7-481c-b6df-5109c1a9bedc&opt=currsel%2Cctxmenu")
SCOPE = ("Official 2025 cabotage region-to-region distribution; original shares of the full "
         "selected panel population, never renormalized by filters. Includes offshore and "
         "undetermined origin categories. Not port-to-port routes, unique consignments or "
         "absolute tonnes; do not multiply by a different handling or annual-report total.")


def prepare(output, source=ROOT / "deployment/brazil_water" / SOURCE_NAME,
            context=ROOT / "deployment/brazil_water" / CONTEXT_NAME):
    source, output = Path(source), Path(output)
    raw = source.read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        raise ValueError("ANTAQ regional pair export differs from reviewed edition")
    context_raw = Path(context).read_bytes()
    if len(context_raw) > 65536 or hashlib.sha256(context_raw).hexdigest() != CONTEXT_HASH:
        raise ValueError("ANTAQ export period evidence differs from reviewed capture")
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != ["Sheet1"]:
            raise ValueError("Unexpected ANTAQ export sheets")
        rows = list(workbook.active.values)
    finally:
        workbook.close()
    if rows[0] != ("Região Origem", "Região Destino", "Distribuição Percentual") or len(rows) != 22:
        raise ValueError("Unexpected ANTAQ regional share headers or coverage")
    data = pl.DataFrame([{"year": 2025, "origin_region": origin, "destination_region": destination,
                          "share_of_cabotage": share} for origin, destination, share in rows[1:]])
    data = data.sort("origin_region", "destination_region")
    csv = data.write_csv().encode()
    metadata = {
        "schema_version": 1, "year": 2025, "unit": "share_fraction", "scope": SCOPE,
        "source": SOURCE, "source_object": "wGpRXf", "reviewed_on": "2026-11-18",
        "panel_updated_at": "2026-04-01 08:17",
        "source_headers": list(rows[0]), "source_rows": 21,
        "filters": {"Carga.NRAno": [2025], "Carga Mês": "unfiltered", "DadosEscala": 1,
                    "origin": "unfiltered", "destination": "unfiltered", "cargo": "unfiltered"},
        "method": "Original Qlik Exportar dados from GR 4.5; paired regional fractions read directly from XLSX, not inferred from marginals",
        "period_evidence": "Year 2025 was selected in the UI; the exported workbook contains no year column",
        "population_headline_displayed_tonnes": 222975436,
        "population_headline_use": "Context only; no absolute-tonnage reconstruction from shares",
        "missing_pairs": "Not reported in this export; never fabricated as zero",
        "files": [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                  for name, content in (("coastal_region_pairs.csv", csv), (SOURCE_NAME, raw),
                                        (CONTEXT_NAME, context_raw))],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "coastal_region_pairs.csv").write_bytes(csv)
    if (output / SOURCE_NAME).resolve() != source.resolve():
        (output / SOURCE_NAME).write_bytes(raw)
    if (output / CONTEXT_NAME).resolve() != Path(context).resolve():
        (output / CONTEXT_NAME).write_bytes(context_raw)
    (output / "coastal_pairs_provenance.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return data.height


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_water")
    parser.add_argument("--source", type=Path, default=ROOT / "deployment/brazil_water" / SOURCE_NAME)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source)} reviewed regional cabotage shares")
