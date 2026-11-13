"""Rebuild Table 12 of the reviewed ANTT TRC 2025 yearbook, PDF page 64.

This is a selected regional flow table, not a complete shipment census or an
operational route network. Chart 45 supplies the monthly all-transport series.
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
MONTHLY_TONNES = [97725063, 108575783, 115207022, 112535948, 122103486, 116901255,
                  128676764, 129625208, 129140024, 92700076, 112840437, 102668585]
PAID_SHARE_PERCENT = [85, 85, 86, 86, 85, 85, 85, 85, 85, 85, 85, 84]


def prepare(output=DEFAULT_ROOT, source_pdf=None):
    if source_pdf is not None and hashlib.sha256(Path(source_pdf).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Road source edition changed; review before updating")
    data = pl.DataFrame(ROWS, schema=["origin_state", "origin_region", "destination_state",
                                    "destination_region", "tonnes", "reported_share_percent"],
                        orient="row").with_columns(pl.lit(2025).alias("year"))
    raw = data.write_csv().encode()
    monthly = pl.DataFrame({"year": [2025] * 12, "month": list(range(1, 13)),
                            "tonnes": MONTHLY_TONNES,
                            "reported_paid_share_percent": PAID_SHARE_PERCENT})
    monthly_raw = monthly.write_csv().encode()
    metadata = {
        "schema_version": 1, "reference_year": 2025,
        "source": {"url": SOURCE, "sha256": SOURCE_SHA256,
                   "edition": "Anuario TRC 2025 v1.1", "pdf_page": 64,
                   "printed_page": 56, "table": 12},
        "monthly_source": {"url": SOURCE, "sha256": SOURCE_SHA256, "pdf_page": 63,
                           "printed_page": 55, "chart": 45,
                           "scope": "MDF-e reported total tonnes, paid plus own-account transport",
                           "precision": "Published integer-tonne chart labels; paid shares rounded to whole percent"},
        "reconciliation": {
            "status": "annual_total_reconstructed_from_monthly_chart",
            "annual_tonnes": sum(MONTHLY_TONNES),
            "annual_method": "Sum of all 12 published Chart 45 total-tonnage labels",
            "summary_rounded_billion_tonnes": 1.4,
            "summary_pdf_page": 61,
            "summary_rounding_billion_tonnes": 0.1,
            "regional_reference_tonnes": 1165000000,
            "regional_reference_use": "Source reference for Table 12 shares only; not the all-transport annual total",
            "regional_scope_status": "The yearbook does not explicitly explain this denominator's difference from Chart 45",
            "paid_tonnage_status": "Not reconstructed: rounded monthly paid shares cannot identify an exact paid-tonnage total",
        },
        "interpretation": "Selected published MDF-e flows between Immediate Geographic Regions (RGIs), not municipal pairs or truck itineraries.",
        "quality_notes": [
            "RGIs group municipalities; a same-region flow can cross municipal boundaries. It is not evidence of an urban-only trip.",
            "Only the 16 published leading flows are covered. Missing pairs are unavailable, not zero; no reverse flow is inferred.",
            "The annual MDF-e series uses the 12 Chart 45 monthly labels, whose sum rounds to the summary's 1.4 billion tonnes. The 1.165 billion regional reference is kept separate.",
            "Shares retain the source rounding and denominator; they are not recalculated against the selected 16-flow subtotal.",
            "MDF-e coverage excludes within-municipality trips. Reported movements need not identify unique cargo.",
        ],
        "files": [{"path": "regional_flows.csv", "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw)},
                  {"path": "monthly.csv", "sha256": hashlib.sha256(monthly_raw).hexdigest(),
                   "bytes": len(monthly_raw)}],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "regional_flows.csv").write_bytes(raw)
    (output / "monthly.csv").write_bytes(monthly_raw)
    (output / "provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    load_road(output)
    return data.height


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source_pdf)} reviewed regional road flows")
