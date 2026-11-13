"""Rebuild Table 12 of the reviewed ANTT TRC 2025 yearbook, PDF page 64.

This is a selected regional flow table, not a complete shipment census or an
operational route network. The conflicting national totals remain unresolved.
"""

import argparse
import hashlib
import json
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road

SOURCE = "https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/anuario_trc_2025_antt.pdf"
SOURCE_SHA256 = "db96f4a5e779261a28e050b165ef84236ddd92d3ac0f0801a12fb04306e03e0b"
ROWS = [
    ("SP", "São Paulo", "SP", "São Paulo", 14403113, 1.24),
    ("MT", "Rondonópolis", "MT", "Sorriso", 9946350, 0.85),
    ("MT", "Sorriso", "MT", "Sorriso", 8478820, 0.73),
    ("RJ", "Rio de Janeiro", "RJ", "Rio de Janeiro", 7859864, 0.67),
    ("BA", "Salvador", "BA", "Salvador", 7238738, 0.62),
    ("PA", "Itaituba", "MT", "Sinop", 6350618, 0.55),
    ("MG", "Belo Horizonte", "MG", "Belo Horizonte", 6136256, 0.53),
    ("BA", "Salvador", "BA", "Barreiras", 5032794, 0.43),
    ("MT", "Rondonópolis", "MT", "Primavera do Leste", 4677980, 0.40),
    ("SP", "São Paulo", "SP", "Santos", 4454680, 0.38),
    ("MT", "Sorriso", "MT", "Cuiabá", 4287972, 0.37),
    ("PA", "Itaituba", "MT", "Sorriso", 4243478, 0.36),
    ("SP", "Santos", "SP", "Santos", 4086654, 0.35),
    ("CE", "Fortaleza", "CE", "Fortaleza", 3736566, 0.32),
    ("MT", "Rondonópolis", "MT", "Rondonópolis", 3631841, 0.31),
    ("PR", "Curitiba", "PR", "Curitiba", 3604563, 0.31),
]


def prepare(output=DEFAULT_ROOT, source_pdf=None):
    if source_pdf is not None and hashlib.sha256(Path(source_pdf).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Road source edition changed; review before updating")
    data = pl.DataFrame(ROWS, schema=["origin_state", "origin_region", "destination_state",
                                    "destination_region", "tonnes", "reported_share_percent"],
                        orient="row").with_columns(pl.lit(2025).alias("year"))
    raw = data.write_csv().encode()
    metadata = {
        "schema_version": 1, "reference_year": 2025,
        "source": {"url": SOURCE, "sha256": SOURCE_SHA256,
                   "edition": "Anuario TRC 2025 v1.1", "pdf_page": 64,
                   "printed_page": 56, "table": 12},
        "interpretation": "Selected published MDF-e flows between Immediate Geographic Regions (RGIs), not municipal pairs or truck itineraries.",
        "quality_notes": [
            "RGIs group municipalities; a same-region flow can cross municipal boundaries. It is not evidence of an urban-only trip.",
            "Only the 16 published leading flows are covered. Missing pairs are unavailable, not zero; no reverse flow is inferred.",
            "The source cites approximately 1.4 billion tonnes on PDF page 61 and 1.165 billion on page 64. National tonnage remains unreconciled.",
            "Shares retain the source rounding and denominator; they are not recalculated against the selected 16-flow subtotal.",
            "MDF-e coverage excludes within-municipality trips. Reported movements need not identify unique cargo.",
        ],
        "files": [{"path": "regional_flows.csv", "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw)}],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "regional_flows.csv").write_bytes(raw)
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    load_road(output)
    return data.height


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source_pdf)} reviewed regional road flows")
